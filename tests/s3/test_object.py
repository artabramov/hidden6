# tests/s3/test_object.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.constants import OBJECT_KEY_MAX_BYTES
from app.s3.paths import resolve_object_path
from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjectKeyConflictError,
    S3ObjectNotFoundError,
)
from app.models.bucket import S3Bucket  # noqa: E402
from app.models.object import S3Object  # noqa: E402
from app.models.object_version import S3ObjectVersion  # noqa: E402
from app.models.user import User  # noqa: E402
from app.s3.object import (  # noqa: E402
    create_object_version,
    load_object,
    object_mkdir,
    upsert_object,
)

load_all_models()


class TestObjectPath(unittest.TestCase):
    def test_resolves_flat_key(self):
        bucket_path, object_path = resolve_object_path(
            "/mnt/buckets",
            "photos",
            "cat.png",
        )

        self.assertEqual(bucket_path, "/mnt/buckets/photos")
        self.assertEqual(object_path, "/mnt/buckets/photos/cat.png")

    def test_resolves_nested_key(self):
        bucket_path, object_path = resolve_object_path(
            "/mnt/buckets",
            "photos",
            "2024/summer/cat.png",
        )

        self.assertEqual(bucket_path, "/mnt/buckets/photos")
        self.assertEqual(
            object_path,
            "/mnt/buckets/photos/2024/summer/cat.png",
        )

    def test_resolves_key_at_max_length(self):
        key = "a" * OBJECT_KEY_MAX_BYTES
        _, object_path = resolve_object_path(
            "/mnt/buckets",
            "photos",
            key,
        )

        self.assertEqual(object_path, f"/mnt/buckets/photos/{key}")

    def test_joins_key_without_normalization(self):
        bucket_path, object_path = resolve_object_path(
            "/mnt/buckets",
            "photos",
            "2024/summer/cat.png",
        )

        self.assertEqual(
            object_path,
            os.path.join(bucket_path, "2024/summer/cat.png"),
        )
        self.assertEqual(
            object_path,
            "/mnt/buckets/photos/2024/summer/cat.png",
        )

    def test_does_not_collapse_parent_segments(self):
        _bucket_path, object_path = resolve_object_path(
            "/mnt/buckets",
            "photos",
            "foo/../bar",
        )

        self.assertEqual(
            object_path,
            "/mnt/buckets/photos/foo/../bar",
        )

    def test_rejects_key_escaping_the_bucket(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_object_path(
                "/mnt/buckets",
                "photos",
                "/etc/passwd",
            )

        self.assertIn("escapes bucket directory", str(ctx.exception))


class TestObjectLoad(unittest.IsolatedAsyncioTestCase):
    async def test_returns_object(self):
        bucket = S3Bucket(id=7, user_id=1, bucket_name="photos")
        s3_object = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="cat.png",
            size_bytes=10,
            etag="abc",
            content_type="image/png",
        )
        repo = MagicMock()
        repo.select = AsyncMock(return_value=s3_object)

        result = await load_object(repo, bucket, "cat.png", "/photos/cat.png")

        self.assertIs(result, s3_object)
        repo.select.assert_awaited_once_with(
            S3Object,
            bucket_id=7,
            object_key="cat.png",
        )

    async def test_delete_marker_raises(self):
        bucket = S3Bucket(id=7, user_id=1, bucket_name="photos")
        s3_object = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="gone.txt",
            delete_marker=True,
        )
        repo = MagicMock()
        repo.select = AsyncMock(return_value=s3_object)

        with self.assertRaises(S3ObjectNotFoundError):
            await load_object(repo, bucket, "gone.txt", "/photos/gone.txt")

    async def test_missing_object_raises(self):
        bucket = S3Bucket(id=7, user_id=1, bucket_name="photos")
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjectNotFoundError):
            await load_object(repo, bucket, "missing.png", "/photos/missing.png")


class TestObjectMkdir(unittest.IsolatedAsyncioTestCase):
    async def _run(self, isdir_value, mkdir_error=None):
        with (
            patch(
                "app.s3.object.isdir",
                new_callable=AsyncMock,
                return_value=isdir_value,
            ),
            patch(
                "app.s3.object.mktree",
                new_callable=AsyncMock,
                side_effect=mkdir_error,
            ) as mkdir_mock,
        ):
            await object_mkdir(
                "/mnt/buckets/photos/2024/cat.png",
                "/photos/2024/cat.png",
            )
        return mkdir_mock

    async def test_creates_key_prefix(self):
        mkdir_mock = await self._run(isdir_value=False)

        mkdir_mock.assert_awaited_once_with(
            "/mnt/buckets/photos/2024",
        )

    async def test_directory_at_key_raises_conflict(self):
        with self.assertRaises(S3ObjectKeyConflictError):
            await self._run(isdir_value=True)

    async def test_file_at_key_prefix_raises_conflict(self):
        with self.assertRaises(S3ObjectKeyConflictError):
            await self._run(
                isdir_value=False,
                mkdir_error=NotADirectoryError(),
            )


class TestObjectUpsert(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.bucket = S3Bucket(id=7, user_id=1, bucket_name="photos")

    def _build_repo(self, existing):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=existing)
        repo.insert = AsyncMock(side_effect=lambda obj: obj)
        repo.update = AsyncMock(side_effect=lambda obj: obj)
        return repo

    async def _upsert(self, repo, *, version_uuid=None):
        return await upsert_object(
            repo=repo,
            bucket=self.bucket,
            user=self.user,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
            version_uuid=version_uuid,
        )

    async def test_inserts_new_object(self):
        repo = self._build_repo(None)

        s3_object = await self._upsert(repo)

        repo.insert.assert_awaited_once_with(s3_object)
        self.assertIsInstance(s3_object, S3Object)
        self.assertEqual(s3_object.bucket_id, 7)
        self.assertEqual(s3_object.user_id, 1)
        self.assertEqual(s3_object.object_key, "2024/cat.png")
        self.assertEqual(s3_object.size_bytes, 12)
        self.assertEqual(s3_object.etag, "etag123")
        self.assertEqual(s3_object.content_type, "image/png")
        self.assertIsNone(s3_object.version_uuid)
        self.assertFalse(s3_object.delete_marker)
        self.assertIsNone(s3_object.lock_mode)
        self.assertIsNone(s3_object.retain_until)

    async def test_updates_existing_object(self):
        existing = S3Object(
            id=3,
            bucket_id=7,
            user_id=99,
            object_key="2024/cat.png",
            size_bytes=1,
            etag="old",
            content_type="text/plain",
        )
        repo = self._build_repo(existing)

        s3_object = await self._upsert(repo)

        self.assertIs(s3_object, existing)
        repo.insert.assert_not_awaited()
        repo.update.assert_awaited_once_with(existing)
        self.assertEqual(existing.user_id, 1)
        self.assertEqual(existing.size_bytes, 12)
        self.assertEqual(existing.etag, "etag123")
        self.assertEqual(existing.content_type, "image/png")
        self.assertIsNone(existing.version_uuid)
        self.assertFalse(existing.delete_marker)
        self.assertIsInstance(existing.modified_at, int)

    async def test_overwrite_clears_delete_marker(self):
        existing = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            delete_marker=True,
        )
        repo = self._build_repo(existing)

        await self._upsert(repo)

        self.assertFalse(existing.delete_marker)
        self.assertEqual(existing.size_bytes, 12)
        self.assertEqual(existing.etag, "etag123")
        self.assertEqual(existing.content_type, "image/png")

    async def test_sets_version_uuid_on_insert(self):
        repo = self._build_repo(None)

        s3_object = await self._upsert(repo, version_uuid="c" * 32)

        self.assertEqual(s3_object.version_uuid, "c" * 32)

    async def test_sets_version_uuid_on_update(self):
        existing = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=1,
            etag="old",
            content_type="text/plain",
            version_uuid="a" * 32,
        )
        repo = self._build_repo(existing)

        await self._upsert(repo, version_uuid="b" * 32)

        self.assertEqual(existing.version_uuid, "b" * 32)

    async def test_applies_bucket_default_retention_days(self):
        self.bucket.object_lock_enabled = True
        self.bucket.default_lock_mode = "GOVERNANCE"
        self.bucket.default_retention_days = 2
        repo = self._build_repo(None)

        with patch("app.s3.bucket.time.time", return_value=1_000_000):
            s3_object = await self._upsert(repo)

        self.assertEqual(s3_object.lock_mode, "GOVERNANCE")
        self.assertEqual(s3_object.retain_until, 1_000_000 + 2 * 86400)
        self.assertFalse(s3_object.legal_hold)

    async def test_applies_bucket_default_retention_years(self):
        self.bucket.object_lock_enabled = True
        self.bucket.default_lock_mode = "COMPLIANCE"
        self.bucket.default_retention_years = 1
        repo = self._build_repo(None)

        with patch("app.s3.bucket.time.time", return_value=1_000_000):
            s3_object = await self._upsert(repo)

        self.assertEqual(s3_object.lock_mode, "COMPLIANCE")
        self.assertEqual(s3_object.retain_until, 1_000_000 + 365 * 86400)

    async def test_overwrite_applies_bucket_default_retention(self):
        self.bucket.object_lock_enabled = True
        self.bucket.default_lock_mode = "GOVERNANCE"
        self.bucket.default_retention_days = 1
        existing = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=1,
            etag="old",
            content_type="text/plain",
            legal_hold=True,
        )
        repo = self._build_repo(existing)

        with patch("app.s3.bucket.time.time", return_value=1_000_000):
            await self._upsert(repo)

        self.assertEqual(existing.lock_mode, "GOVERNANCE")
        self.assertEqual(existing.retain_until, 1_000_000 + 86400)
        self.assertFalse(existing.legal_hold)

    async def test_overwrite_clears_lock_without_bucket_default(self):
        existing = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=1,
            etag="old",
            content_type="text/plain",
            lock_mode="COMPLIANCE",
            retain_until=999,
            legal_hold=True,
        )
        repo = self._build_repo(existing)

        await self._upsert(repo)

        self.assertIsNone(existing.lock_mode)
        self.assertIsNone(existing.retain_until)
        self.assertFalse(existing.legal_hold)


class TestCreateObjectVersion(unittest.IsolatedAsyncioTestCase):
    def _build_repo(self):
        repo = MagicMock()
        repo.insert = AsyncMock(side_effect=lambda obj: obj)
        return repo

    def _s3_object(self, **kwargs) -> S3Object:
        defaults = {
            "id": 3,
            "bucket_id": 7,
            "user_id": 1,
            "object_key": "2024/cat.png",
            "modified_at": 1_704_067_200,
            "size_bytes": 12,
            "etag": "etag123",
            "content_type": "image/png",
            "version_uuid": "a" * 32,
            "delete_marker": False,
            "lock_mode": None,
            "retain_until": None,
            "legal_hold": False,
        }
        defaults.update(kwargs)
        return S3Object(**defaults)

    async def test_preserves_current_object_state(self):
        s3_object = self._s3_object(
            lock_mode="COMPLIANCE",
            retain_until=1_704_153_600,
            legal_hold=True,
        )
        repo = self._build_repo()

        version = await create_object_version(repo, s3_object)

        repo.insert.assert_awaited_once_with(version)
        self.assertIsInstance(version, S3ObjectVersion)
        self.assertEqual(version.object_id, 3)
        self.assertEqual(version.user_id, 1)
        self.assertEqual(version.modified_at, 1_704_067_200)
        self.assertEqual(version.version_uuid, "a" * 32)
        self.assertEqual(version.size_bytes, 12)
        self.assertEqual(version.etag, "etag123")
        self.assertEqual(version.content_type, "image/png")
        self.assertFalse(version.delete_marker)
        self.assertEqual(version.lock_mode, "COMPLIANCE")
        self.assertEqual(version.retain_until, 1_704_153_600)
        self.assertTrue(version.legal_hold)

    async def test_preserves_null_version_uuid(self):
        s3_object = self._s3_object(version_uuid=None)
        repo = self._build_repo()

        version = await create_object_version(repo, s3_object)

        self.assertIsNone(version.version_uuid)

    async def test_preserves_delete_marker(self):
        s3_object = self._s3_object(
            version_uuid="d" * 32,
            delete_marker=True,
            size_bytes=None,
            etag=None,
            content_type=None,
        )
        repo = self._build_repo()

        version = await create_object_version(repo, s3_object)

        self.assertTrue(version.delete_marker)
        self.assertIsNone(version.size_bytes)
        self.assertIsNone(version.etag)
        self.assertIsNone(version.content_type)
