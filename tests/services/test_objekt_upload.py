# tests/services/test_objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3BucketNotFoundError,
    S3ObjektKeyConflictError,
    S3ObjektKeyInvalidError,
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
        self.log = self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.body = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
        )

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

    def _build_mocks(self, mimetype="image/png"):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        self.repo = MagicMock()
        self.repo.commit = AsyncMock()
        self.repo.rollback = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch("uuid.uuid4", return_value=MagicMock(hex="beef"))
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=self._build_lock_context(),
        )
        self.bucket_load = self._patch(
            "bucket_load",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.objekt_mkdir = self._patch(
            "objekt_mkdir",
            new_callable=AsyncMock,
        )
        self.objekt_upsert = self._patch(
            "objekt_upsert",
            new_callable=AsyncMock,
            return_value=self.objekt,
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
        self.rename = self._patch("rename", new_callable=AsyncMock)
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.emit = self._patch("hooks.emit", new_callable=AsyncMock)

    async def _upload(self, key="2024/cat.png"):
        return await objekt_upload(
            session=self.session,
            current_user=self.user,
            bucket_name="photos",
            objekt_key=key,
            body=self.body,
        )

    async def test_stages_and_publishes_object(self):
        self._build_mocks()

        objekt = await self._upload()

        self.upload.assert_awaited_once_with(self.body, "/mnt/tmp/beef")
        self.lock.assert_called_once_with(
            "/mnt/buckets/photos",
            LockType.WRITE,
        )
        self.isdir.assert_awaited_once_with("/mnt/buckets/photos")
        self.objekt_mkdir.assert_awaited_once_with(
            "/mnt/buckets/photos/2024/cat.png",
            "/photos/2024/cat.png",
        )
        self.rename.assert_awaited_once_with(
            "/mnt/tmp/beef",
            "/mnt/buckets/photos/2024/cat.png",
        )
        self.repo.commit.assert_awaited_once()
        self.assertIs(objekt, self.objekt)
        self.emit.assert_awaited_once_with(
            Events.OBJEKT_UPLOADED,
            objekt,
        )

    async def test_upserts_metadata_of_staged_body(self):
        self._build_mocks()

        await self._upload()

        kwargs = self.objekt_upsert.await_args.kwargs
        self.assertIs(kwargs["bucket"], self.bucket)
        self.assertIs(kwargs["user"], self.user)
        self.assertEqual(kwargs["object_key"], "2024/cat.png")
        self.assertEqual(kwargs["size_bytes"], 12)
        self.assertEqual(kwargs["etag"], "etag123")
        self.assertEqual(kwargs["content_type"], "image/png")

    async def test_unknown_mimetype_falls_back_to_octet_stream(self):
        self._build_mocks(mimetype=None)

        await self._upload()

        self.assertEqual(
            self.objekt_upsert.await_args.kwargs["content_type"],
            "application/octet-stream",
        )

    async def test_inaccessible_bucket_stops_before_upload(self):
        self._build_mocks()
        self.bucket_load.side_effect = S3BucketNotFoundError("/photos")

        with self.assertRaises(S3BucketNotFoundError):
            await self._upload()

        self.upload.assert_not_awaited()

    async def test_missing_bucket_dir_cleans_staged_file(self):
        self._build_mocks()
        self.isdir.return_value = False

        with self.assertRaises(S3BucketNotFoundError):
            await self._upload()

        self.rename.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_key_conflict_cleans_staged_file(self):
        self._build_mocks()
        self.objekt_mkdir.side_effect = S3ObjektKeyConflictError()

        with self.assertRaises(S3ObjektKeyConflictError):
            await self._upload()

        self.rename.assert_not_awaited()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_directory_at_object_path_is_a_key_conflict(self):
        self._build_mocks()
        self.rename.side_effect = IsADirectoryError()

        with self.assertRaises(S3ObjektKeyConflictError):
            await self._upload()

        self.repo.commit.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_object_at_key_prefix_is_a_key_conflict(self):
        self._build_mocks()
        self.rename.side_effect = NotADirectoryError()

        with self.assertRaises(S3ObjektKeyConflictError):
            await self._upload()

        self.repo.commit.assert_not_awaited()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_failed_upload_cleans_staged_file(self):
        self._build_mocks()
        self.upload.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")
        self.emit.assert_not_awaited()

    async def test_logs_when_rollback_fails(self):
        self._build_mocks()
        self.upload.side_effect = RuntimeError("disk full")
        self.repo.rollback.side_effect = RuntimeError("session closed")

        with self.assertRaises(RuntimeError) as cm:
            await self._upload()

        self.assertEqual(str(cm.exception), "disk full")
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")
        self.log.exception.assert_called_once()
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_cleanup_fails(self):
        self._build_mocks()
        self.upload.side_effect = RuntimeError("disk full")
        self.delete.side_effect = OSError("busy")

        with self.assertRaises(RuntimeError) as cm:
            await self._upload()

        self.assertEqual(str(cm.exception), "disk full")
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")
        self.log.exception.assert_called_once()
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_rollback_and_cleanup_failures(self):
        self._build_mocks()
        self.rename.side_effect = IsADirectoryError()
        self.repo.rollback.side_effect = RuntimeError("session closed")
        self.delete.side_effect = OSError("busy")

        with self.assertRaises(S3ObjektKeyConflictError):
            await self._upload()

        self.repo.commit.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/beef")
        messages = [
            call.args[0] for call in self.log.exception.call_args_list
        ]
        self.assertEqual(len(messages), 2)
        self.assertIn("msg=rollback_failed", messages[0])
        self.assertIn("msg=cleanup_failed", messages[1])

    async def test_rejects_key_escaping_the_bucket(self):
        self._build_mocks()

        with self.assertRaises(S3ObjektKeyInvalidError) as cm:
            await self._upload(key="../../etc/passwd")

        self.assertEqual(
            cm.exception.resource,
            "/photos/../../etc/passwd",
        )
        self.bucket_load.assert_not_awaited()
        self.upload.assert_not_awaited()
