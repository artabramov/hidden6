# tests/services/test_objekt_store.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3ObjektKeyConflictError,
    S3ObjektKeyInvalidError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.objekt_store import (  # noqa: E402
    assert_bucket_dir,
    load_bucket,
    mkdir_object_parent,
    resolve_object_path,
    upsert_objekt,
)

load_all_models()


class TestLoadBucket(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.root = User(id=2, username="root", is_root=True)

    def _build_repo(self, bucket):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=bucket)
        return repo

    async def test_returns_own_bucket(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")

        result = await load_bucket(
            self._build_repo(bucket),
            "photos",
            self.user,
            "/photos",
        )

        self.assertIs(result, bucket)

    async def test_returns_foreign_bucket_for_root(self):
        bucket = Bucket(id=7, user_id=99, bucket_name="photos")

        result = await load_bucket(
            self._build_repo(bucket),
            "photos",
            self.root,
            "/photos",
        )

        self.assertIs(result, bucket)

    async def test_missing_bucket_raises(self):
        with self.assertRaises(S3BucketNotFoundError):
            await load_bucket(
                self._build_repo(None),
                "photos",
                self.user,
                "/photos",
            )

    async def test_foreign_bucket_is_denied(self):
        bucket = Bucket(id=7, user_id=99, bucket_name="photos")

        with self.assertRaises(S3AccessDeniedError):
            await load_bucket(
                self._build_repo(bucket),
                "photos",
                self.user,
                "/photos",
            )


class TestResolveObjectPath(unittest.TestCase):
    def test_maps_flat_key(self):
        path = resolve_object_path(
            "/mnt/buckets/photos",
            "cat.png",
            "/photos/cat.png",
        )

        self.assertEqual(path, "/mnt/buckets/photos/cat.png")

    def test_maps_nested_key(self):
        path = resolve_object_path(
            "/mnt/buckets/photos",
            "2024/summer/cat.png",
            "/photos/2024/summer/cat.png",
        )

        self.assertEqual(
            path,
            "/mnt/buckets/photos/2024/summer/cat.png",
        )

    def test_rejects_key_escaping_the_bucket(self):
        with self.assertRaises(S3ObjektKeyInvalidError):
            resolve_object_path(
                "/mnt/buckets/photos",
                "../videos/cat.png",
                "/photos/../videos/cat.png",
            )

    def test_rejects_key_resolving_to_the_bucket(self):
        with self.assertRaises(S3ObjektKeyInvalidError):
            resolve_object_path(
                "/mnt/buckets/photos",
                "2024/..",
                "/photos/2024/..",
            )


class TestAssertBucketDir(unittest.IsolatedAsyncioTestCase):
    async def test_passes_for_existing_dir(self):
        with patch(
            "app.services.objekt_store.isdir",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await assert_bucket_dir("/mnt/buckets/photos", "/photos")

    async def test_missing_dir_raises(self):
        with patch(
            "app.services.objekt_store.isdir",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with self.assertRaises(S3BucketNotFoundError):
                await assert_bucket_dir("/mnt/buckets/photos", "/photos")


class TestMkdirObjectParent(unittest.IsolatedAsyncioTestCase):
    async def _run(self, isdir_value, mkdir_error=None):
        with (
            patch(
                "app.services.objekt_store.isdir",
                new_callable=AsyncMock,
                return_value=isdir_value,
            ),
            patch(
                "app.services.objekt_store.mkdir",
                new_callable=AsyncMock,
                side_effect=mkdir_error,
            ) as mkdir_mock,
        ):
            await mkdir_object_parent(
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
        with self.assertRaises(S3ObjektKeyConflictError):
            await self._run(isdir_value=True)

    async def test_file_at_key_prefix_raises_conflict(self):
        with self.assertRaises(S3ObjektKeyConflictError):
            await self._run(
                isdir_value=False,
                mkdir_error=NotADirectoryError(),
            )


class TestUpsertObjekt(unittest.IsolatedAsyncioTestCase):
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
        return await upsert_objekt(
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
