# tests/services/test_objekt_upload.py
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
)
from app.hooks import Events  # noqa: E402
from app.locks import LockType  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.objekt_upload import objekt_upload  # noqa: E402

load_all_models()


class TestObjektUpload(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.root = User(id=2, username="root", is_root=True)
        self.session = MagicMock()
        self.body = MagicMock()

    def _patch(self, target, **kwargs):
        patcher = patch(f"app.services.objekt_upload.{target}", **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _build_lock_context(self):
        ctx = AsyncMock()
        ctx.__aenter__.return_value = None
        ctx.__aexit__.return_value = None
        return ctx

    def _build_repo(self, *select_results):
        repo = MagicMock()
        repo.select = AsyncMock(side_effect=list(select_results))
        repo.insert = AsyncMock(side_effect=lambda obj: obj)
        repo.update = AsyncMock(side_effect=lambda obj: obj)
        repo.commit = AsyncMock()
        repo.rollback = AsyncMock()
        return repo

    def _build_mocks(
        self,
        repo,
        isdir_results=(True, False),
        mimetype="image/png",
    ):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=repo)
        self._patch("uuid.uuid4", return_value=MagicMock(hex="beef"))
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=self._build_lock_context(),
        )
        self.upload = self._patch("upload", new_callable=AsyncMock)
        self._patch(
            "get_filesize",
            new_callable=AsyncMock,
            return_value=12,
        )
        self._patch(
            "get_file_hash",
            new_callable=AsyncMock,
            return_value="etag123",
        )
        self._patch(
            "get_mimetype",
            new_callable=AsyncMock,
            return_value=mimetype,
        )
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            side_effect=list(isdir_results),
        )
        self.mkdir = self._patch("mkdir", new_callable=AsyncMock)
        self.rename = self._patch("rename", new_callable=AsyncMock)
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.emit = self._patch("hooks.emit", new_callable=AsyncMock)

    async def _upload(self, user=None, key="2024/cat.png"):
        return await objekt_upload(
            bucket_name="photos",
            object_key=key,
            user=user or self.user,
            session=self.session,
            body=self.body,
        )

    async def test_stages_and_publishes_new_object(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=1, bucket_name="photos"),
            None,
        )
        self._build_mocks(repo)

        objekt = await self._upload()

        self.upload.assert_awaited_once_with(self.body, "/mnt/tmp/beef")
        self.lock.assert_called_once_with(
            "/mnt/buckets/photos",
            LockType.WRITE,
        )
        self.mkdir.assert_awaited_once_with("/mnt/buckets/photos/2024")
        self.rename.assert_awaited_once_with(
            "/mnt/tmp/beef",
            "/mnt/buckets/photos/2024/cat.png",
        )
        repo.insert.assert_awaited_once_with(objekt)
        repo.commit.assert_awaited_once()
        self.assertIsInstance(objekt, Objekt)
        self.assertEqual(objekt.bucket_id, 7)
        self.assertEqual(objekt.user_id, 1)
        self.assertEqual(objekt.object_key, "2024/cat.png")
        self.assertEqual(objekt.size_bytes, 12)
        self.assertEqual(objekt.etag, "etag123")
        self.assertEqual(objekt.content_type, "image/png")
        self.emit.assert_awaited_once_with(
            Events.OBJEKT_UPLOADED,
            objekt,
        )

    async def test_overwrite_updates_existing_row(self):
        existing = Objekt(
            id=3,
            bucket_id=7,
            user_id=99,
            object_key="2024/cat.png",
            size_bytes=1,
            etag="old",
            content_type="text/plain",
        )
        repo = self._build_repo(
            Bucket(id=7, user_id=1, bucket_name="photos"),
            existing,
        )
        self._build_mocks(repo)

        objekt = await self._upload()

        self.assertIs(objekt, existing)
        repo.insert.assert_not_awaited()
        repo.update.assert_awaited_once_with(existing)
        self.assertEqual(existing.user_id, 1)
        self.assertEqual(existing.size_bytes, 12)
        self.assertEqual(existing.etag, "etag123")
        self.assertEqual(existing.content_type, "image/png")

    async def test_unknown_mimetype_falls_back_to_octet_stream(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=1, bucket_name="photos"),
            None,
        )
        self._build_mocks(repo, mimetype=None)

        objekt = await self._upload()

        self.assertEqual(
            objekt.content_type,
            "application/octet-stream",
        )

    async def test_root_uploads_into_foreign_bucket(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=99, bucket_name="photos"),
            None,
        )
        self._build_mocks(repo)

        objekt = await self._upload(user=self.root)

        self.assertEqual(objekt.user_id, 2)

    async def test_missing_bucket_row_raises(self):
        repo = self._build_repo(None)
        self._build_mocks(repo)

        with self.assertRaises(S3BucketNotFoundError):
            await self._upload()

        self.upload.assert_not_awaited()

    async def test_foreign_bucket_is_denied(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=99, bucket_name="photos"),
        )
        self._build_mocks(repo)

        with self.assertRaises(S3AccessDeniedError):
            await self._upload()

        self.upload.assert_not_awaited()

    async def test_missing_bucket_dir_raises_and_cleans_staged(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=1, bucket_name="photos"),
        )
        self._build_mocks(repo, isdir_results=(False,))

        with self.assertRaises(S3BucketNotFoundError):
            await self._upload()

        self.rename.assert_not_awaited()
        repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_directory_at_key_raises_conflict(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=1, bucket_name="photos"),
        )
        self._build_mocks(repo, isdir_results=(True, True))

        with self.assertRaises(S3ObjektKeyConflictError):
            await self._upload()

        self.rename.assert_not_awaited()

    async def test_file_at_key_prefix_raises_conflict(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=1, bucket_name="photos"),
        )
        self._build_mocks(repo)
        self.mkdir.side_effect = NotADirectoryError()

        with self.assertRaises(S3ObjektKeyConflictError):
            await self._upload()

        self.rename.assert_not_awaited()

    async def test_failed_upload_cleans_staged_file(self):
        repo = self._build_repo(
            Bucket(id=7, user_id=1, bucket_name="photos"),
        )
        self._build_mocks(repo)
        self.upload.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            await self._upload()

        repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")
        self.emit.assert_not_awaited()
