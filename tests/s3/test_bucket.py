# tests/s3/test_bucket.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock

from app.errors import S3InvalidBucketNameError
from app.s3.bucket import bucket_dir
from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3AccessDeniedError,
    S3BucketNotFoundError,
)
from app.constants import BUCKET_VERSIONING_ENABLED  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.s3.bucket import bucket_default_object_lock, bucket_load  # noqa: E402

load_all_models()


class TestBucketDir(unittest.TestCase):
    def _assert_rejects(self, bucket_name):
        resource = f"/{bucket_name}"

        with self.assertRaises(S3InvalidBucketNameError) as ctx:
            bucket_dir("/mnt/buckets", bucket_name, resource)

        self.assertEqual(ctx.exception.resource, resource)

    def test_resolves_shortest_name(self):
        self.assertEqual(
            bucket_dir("/mnt/buckets", "abc", "/abc"),
            "/mnt/buckets/abc",
        )

    def test_resolves_dashes_and_periods(self):
        self.assertEqual(
            bucket_dir("/mnt/buckets", "my-bucket.1", "/my-bucket.1"),
            "/mnt/buckets/my-bucket.1",
        )

    def test_resolves_longest_name(self):
        name = "a" * 63
        self.assertEqual(
            bucket_dir("/mnt/buckets", name, f"/{name}"),
            f"/mnt/buckets/{name}",
        )

    def test_rejects_empty_name(self):
        self._assert_rejects("")

    def test_rejects_too_short(self):
        self._assert_rejects("ab")

    def test_rejects_too_long(self):
        self._assert_rejects("a" * 64)

    def test_rejects_uppercase(self):
        self._assert_rejects("MyBucket")

    def test_rejects_underscore(self):
        self._assert_rejects("Bad_Name")

    def test_rejects_leading_dash(self):
        self._assert_rejects("-bucket")

    def test_rejects_adjacent_periods(self):
        self._assert_rejects("my..bucket")

    def test_rejects_period_next_to_dash(self):
        self._assert_rejects("my.-bucket")
        self._assert_rejects("my-.bucket")

    def test_rejects_ip_address(self):
        self._assert_rejects("192.168.1.1")


class TestBucketLoad(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.root = User(id=2, username="root", is_root=True)

    def _build_repo(self, bucket):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=bucket)
        return repo

    async def test_returns_own_bucket(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")

        result = await bucket_load(
            self._build_repo(bucket),
            "photos",
            self.user,
            "/photos",
        )

        self.assertIs(result, bucket)

    async def test_returns_foreign_bucket_for_root(self):
        bucket = Bucket(id=7, user_id=99, bucket_name="photos")

        result = await bucket_load(
            self._build_repo(bucket),
            "photos",
            self.root,
            "/photos",
        )

        self.assertIs(result, bucket)

    async def test_missing_bucket_raises(self):
        with self.assertRaises(S3BucketNotFoundError):
            await bucket_load(
                self._build_repo(None),
                "photos",
                self.user,
                "/photos",
            )

    async def test_foreign_bucket_is_denied(self):
        bucket = Bucket(id=7, user_id=99, bucket_name="photos")

        with self.assertRaises(S3AccessDeniedError):
            await bucket_load(
                self._build_repo(bucket),
                "photos",
                self.user,
                "/photos",
            )


class TestBucketDefaultObjectLock(unittest.TestCase):
    def test_returns_none_when_lock_disabled(self):
        bucket = Bucket(user_id=1, bucket_name="photos")

        self.assertEqual(bucket_default_object_lock(bucket), (None, None))

    def test_returns_none_when_no_default_rule(self):
        bucket = Bucket(
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
        )

        self.assertEqual(bucket_default_object_lock(bucket), (None, None))

    def test_computes_retain_until_from_days(self):
        bucket = Bucket(
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
            default_lock_mode="GOVERNANCE",
            default_retention_days=10,
        )

        mode, until = bucket_default_object_lock(bucket, now=1000)

        self.assertEqual(mode, "GOVERNANCE")
        self.assertEqual(until, 1000 + 10 * 86400)

    def test_computes_retain_until_from_years(self):
        bucket = Bucket(
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
            default_lock_mode="COMPLIANCE",
            default_retention_years=2,
        )

        mode, until = bucket_default_object_lock(bucket, now=1000)

        self.assertEqual(mode, "COMPLIANCE")
        self.assertEqual(until, 1000 + 2 * 365 * 86400)
