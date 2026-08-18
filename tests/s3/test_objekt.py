# tests/s3/test_objekt.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.constants import OBJECT_KEY_MAX_BYTES
from app.s3.paths import resolve_objekt_path
from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjectKeyConflictError,
    S3ObjectNotFoundError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.object import Objekt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.s3.object import load_object, object_mkdir, upsert_object  # noqa: E402

load_all_models()


class TestObjektPath(unittest.TestCase):
    def test_resolves_flat_key(self):
        bucket_path, object_path = resolve_objekt_path(
            "/mnt/buckets",
            "photos",
            "cat.png",
        )

        self.assertEqual(bucket_path, "/mnt/buckets/photos")
        self.assertEqual(object_path, "/mnt/buckets/photos/cat.png")

    def test_resolves_nested_key(self):
        bucket_path, object_path = resolve_objekt_path(
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
        _, object_path = resolve_objekt_path(
            "/mnt/buckets",
            "photos",
            key,
        )

        self.assertEqual(object_path, f"/mnt/buckets/photos/{key}")

    def test_joins_key_without_normalization(self):
        bucket_path, object_path = resolve_objekt_path(
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
        _bucket_path, object_path = resolve_objekt_path(
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
            resolve_objekt_path(
                "/mnt/buckets",
                "photos",
                "/etc/passwd",
            )

        self.assertIn("escapes bucket directory", str(ctx.exception))


class TestObjektLoad(unittest.IsolatedAsyncioTestCase):
    async def test_returns_objekt(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="cat.png",
            size_bytes=10,
            etag="abc",
            content_type="image/png",
        )
        repo = MagicMock()
        repo.select = AsyncMock(return_value=objekt)

        result = await load_object(repo, bucket, "cat.png", "/photos/cat.png")

        self.assertIs(result, objekt)
        repo.select.assert_awaited_once_with(
            Objekt,
            bucket_id=7,
            object_key="cat.png",
        )

    async def test_delete_marker_raises(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="gone.txt",
            delete_marker=True,
        )
        repo = MagicMock()
        repo.select = AsyncMock(return_value=objekt)

        with self.assertRaises(S3ObjectNotFoundError):
            await load_object(repo, bucket, "gone.txt", "/photos/gone.txt")

    async def test_missing_objekt_raises(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjectNotFoundError):
            await load_object(repo, bucket, "missing.png", "/photos/missing.png")


class TestObjektMkdir(unittest.IsolatedAsyncioTestCase):
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


class TestObjektUpsert(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")

    def _build_repo(self, existing):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=existing)
        repo.insert = AsyncMock(side_effect=lambda obj: obj)
        repo.update = AsyncMock(side_effect=lambda obj: obj)
        return repo

    async def _upsert(self, repo):
        return await upsert_object(
            repo=repo,
            bucket=self.bucket,
            user=self.user,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
        )

    async def test_inserts_new_objekt(self):
        repo = self._build_repo(None)

        objekt = await self._upsert(repo)

        repo.insert.assert_awaited_once_with(objekt)
        self.assertIsInstance(objekt, Objekt)
        self.assertEqual(objekt.bucket_id, 7)
        self.assertEqual(objekt.user_id, 1)
        self.assertEqual(objekt.object_key, "2024/cat.png")
        self.assertEqual(objekt.size_bytes, 12)
        self.assertEqual(objekt.etag, "etag123")
        self.assertEqual(objekt.content_type, "image/png")
        self.assertFalse(objekt.delete_marker)
        self.assertIsNone(objekt.lock_mode)
        self.assertIsNone(objekt.retain_until)

    async def test_updates_existing_objekt(self):
        existing = Objekt(
            id=3,
            bucket_id=7,
            user_id=99,
            object_key="2024/cat.png",
            size_bytes=1,
            etag="old",
            content_type="text/plain",
        )
        repo = self._build_repo(existing)

        objekt = await self._upsert(repo)

        self.assertIs(objekt, existing)
        repo.insert.assert_not_awaited()
        repo.update.assert_awaited_once_with(existing)
        self.assertEqual(existing.user_id, 1)
        self.assertEqual(existing.size_bytes, 12)
        self.assertEqual(existing.etag, "etag123")
        self.assertEqual(existing.content_type, "image/png")
        self.assertFalse(existing.delete_marker)
        self.assertIsInstance(existing.modified_at, int)

    async def test_overwrite_clears_delete_marker(self):
        existing = Objekt(
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

    async def test_applies_bucket_default_retention_days(self):
        self.bucket.object_lock_enabled = True
        self.bucket.default_lock_mode = "GOVERNANCE"
        self.bucket.default_retention_days = 2
        repo = self._build_repo(None)

        with patch("app.s3.bucket.time.time", return_value=1_000_000):
            objekt = await self._upsert(repo)

        self.assertEqual(objekt.lock_mode, "GOVERNANCE")
        self.assertEqual(objekt.retain_until, 1_000_000 + 2 * 86400)
        self.assertFalse(objekt.legal_hold)

    async def test_applies_bucket_default_retention_years(self):
        self.bucket.object_lock_enabled = True
        self.bucket.default_lock_mode = "COMPLIANCE"
        self.bucket.default_retention_years = 1
        repo = self._build_repo(None)

        with patch("app.s3.bucket.time.time", return_value=1_000_000):
            objekt = await self._upsert(repo)

        self.assertEqual(objekt.lock_mode, "COMPLIANCE")
        self.assertEqual(objekt.retain_until, 1_000_000 + 365 * 86400)

    async def test_overwrite_applies_bucket_default_retention(self):
        self.bucket.object_lock_enabled = True
        self.bucket.default_lock_mode = "GOVERNANCE"
        self.bucket.default_retention_days = 1
        existing = Objekt(
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
        existing = Objekt(
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
