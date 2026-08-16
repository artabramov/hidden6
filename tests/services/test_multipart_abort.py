# tests/services/test_multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3BucketNotFoundError,
    S3ObjektKeyInvalidError,
    S3ObjektUploadNotFoundError,
)
from app.locks import LockType  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.multipart_abort import multipart_abort  # noqa: E402

load_all_models()

UPLOAD_PATH = "/mnt/tmp/beef"
CLEANUP_PATH = "/mnt/tmp/.beef.aborted.cafebabe"


class TestMultipartAbort(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(
            f"app.services.multipart_abort.{target}",
            **kwargs,
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.log = self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )

        config = MagicMock()
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        self.repo = MagicMock()
        self.repo.delete = AsyncMock()
        self.repo.commit = AsyncMock()
        self.repo.rollback = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch(
            "uuid.uuid4",
            return_value=MagicMock(hex="cafebabe"),
        )
        self.load_bucket = self._patch(
            "load_bucket",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.load_multipart = self._patch(
            "load_multipart",
            new_callable=AsyncMock,
            return_value=self.multipart,
        )
        self.parts_delete = self._patch(
            "delete_multipart_parts",
            new_callable=AsyncMock,
        )
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.rename = self._patch("rename", new_callable=AsyncMock)
        self.rmtree = self._patch("rmtree", new_callable=AsyncMock)

        lock_context = AsyncMock()
        lock_context.__aenter__.return_value = None
        lock_context.__aexit__.return_value = None
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=lock_context,
        )

    async def _abort(self):
        await multipart_abort(
            session=self.session,
            current_user=self.user,
            bucket_name="photos",
            objekt_key="2024/cat.png",
            upload_id="beef",
        )

    async def test_renames_then_drops_parts_and_upload(self):
        await self._abort()

        self.lock.assert_called_once_with(UPLOAD_PATH, LockType.WRITE)
        self.rename.assert_awaited_once_with(UPLOAD_PATH, CLEANUP_PATH)
        self.parts_delete.assert_awaited_once_with(
            self.repo,
            self.multipart,
        )
        self.repo.delete.assert_awaited_once_with(self.multipart)
        self.repo.commit.assert_awaited_once()
        self.rmtree.assert_awaited_once_with(CLEANUP_PATH)

    async def test_missing_upload_dir_still_drops_db_rows(self):
        self.isdir.return_value = False

        await self._abort()

        self.rename.assert_not_awaited()
        self.parts_delete.assert_awaited_once()
        self.repo.delete.assert_awaited_once_with(self.multipart)
        self.repo.commit.assert_awaited_once()
        self.rmtree.assert_not_awaited()

    async def test_commit_failure_restores_upload_dir(self):
        self.repo.commit.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._abort()

        self.assertEqual(
            self.rename.await_args_list,
            [
                call(UPLOAD_PATH, CLEANUP_PATH),
                call(CLEANUP_PATH, UPLOAD_PATH),
            ],
        )
        self.repo.rollback.assert_awaited_once()
        self.rmtree.assert_not_awaited()

    async def test_parts_delete_failure_restores_upload_dir(self):
        self.parts_delete.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._abort()

        self.assertEqual(
            self.rename.await_args_list,
            [
                call(UPLOAD_PATH, CLEANUP_PATH),
                call(CLEANUP_PATH, UPLOAD_PATH),
            ],
        )
        self.repo.delete.assert_not_awaited()
        self.repo.commit.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.rmtree.assert_not_awaited()

    async def test_unknown_upload_does_not_touch_filesystem(self):
        self.load_multipart.side_effect = S3ObjektUploadNotFoundError()

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._abort()

        self.rename.assert_not_awaited()
        self.repo.delete.assert_not_awaited()
        self.rmtree.assert_not_awaited()

    async def test_inaccessible_bucket_stops_before_lock(self):
        self.load_bucket.side_effect = S3BucketNotFoundError()

        with self.assertRaises(S3BucketNotFoundError):
            await self._abort()

        self.lock.assert_not_called()
        self.repo.delete.assert_not_awaited()

    async def test_invalid_key_stops_before_cleanup(self):
        with self.assertRaises(S3ObjektKeyInvalidError) as cm:
            await multipart_abort(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                objekt_key="../etc/passwd",
                upload_id="beef",
            )

        self.assertEqual(cm.exception.resource, "/photos/../etc/passwd")
        self.load_bucket.assert_not_awaited()
        self.lock.assert_not_called()
        self.rmtree.assert_not_awaited()

    async def test_logs_when_post_commit_cleanup_fails(self):
        self.rmtree.side_effect = OSError("busy")

        await self._abort()

        self.repo.commit.assert_awaited_once()
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "cleanup_path=%s",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_restore_fails(self):
        self.repo.commit.side_effect = RuntimeError("db down")
        self.rename.side_effect = [None, OSError("busy")]

        with self.assertRaises(RuntimeError):
            await self._abort()

        self.assertIn(
            "msg=restore_failed",
            self.log.exception.call_args.args[0],
        )
        self.rmtree.assert_not_awaited()

    async def test_logs_when_rollback_fails(self):
        self.repo.commit.side_effect = RuntimeError("db down")
        self.repo.rollback.side_effect = RuntimeError("session closed")

        with self.assertRaises(RuntimeError) as cm:
            await self._abort()

        self.assertEqual(str(cm.exception), "db down")
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args_list[0].args[0],
        )
        self.assertEqual(
            self.rename.await_args_list,
            [
                call(UPLOAD_PATH, CLEANUP_PATH),
                call(CLEANUP_PATH, UPLOAD_PATH),
            ],
        )
