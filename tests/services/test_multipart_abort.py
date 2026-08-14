# tests/services/test_multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

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
        self.bucket_load = self._patch(
            "bucket_load",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.multipart_load = self._patch(
            "multipart_load",
            new_callable=AsyncMock,
            return_value=self.multipart,
        )
        self.parts_delete = self._patch(
            "multipart_parts_delete",
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
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
            upload_id="beef",
        )

    async def test_renames_then_drops_parts_and_upload(self):
        await self._abort()

        cleanup = "/mnt/tmp/.beef.aborted.cafebabe"
        self.lock.assert_called_once_with(
            "/mnt/tmp/beef",
            LockType.WRITE,
        )
        self.rename.assert_awaited_once_with("/mnt/tmp/beef", cleanup)
        self.parts_delete.assert_awaited_once_with(
            self.repo,
            self.multipart,
        )
        self.repo.delete.assert_awaited_once_with(self.multipart)
        self.repo.commit.assert_awaited_once()
        self.rmtree.assert_awaited_once_with(cleanup)

    async def test_missing_upload_dir_still_drops_db_rows(self):
        self.isdir.return_value = False

        await self._abort()

        self.rename.assert_not_awaited()
        self.parts_delete.assert_awaited_once()
        self.repo.delete.assert_awaited_once_with(self.multipart)
        self.repo.commit.assert_awaited_once()
        self.rmtree.assert_not_awaited()

    async def test_failed_cleanup_is_logged(self):
        self.rmtree.side_effect = OSError("busy")

        await self._abort()

        self.log.exception.assert_called_once()
        self.repo.commit.assert_awaited_once()

    async def test_db_failure_after_rename_rolls_back(self):
        self.repo.commit.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._abort()

        self.repo.rollback.assert_awaited_once()
        self.rmtree.assert_not_awaited()

    async def test_inaccessible_bucket_raises(self):
        self.bucket_load.side_effect = S3BucketNotFoundError()

        with self.assertRaises(S3BucketNotFoundError):
            await self._abort()

        self.repo.delete.assert_not_awaited()

    async def test_unknown_upload_raises(self):
        self.multipart_load.side_effect = S3ObjektUploadNotFoundError()

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._abort()

        self.repo.delete.assert_not_awaited()
        self.rmtree.assert_not_awaited()

    async def test_invalid_key_stops_before_cleanup(self):
        with self.assertRaises(S3ObjektKeyInvalidError) as cm:
            await multipart_abort(
                bucket_name="photos",
                object_key="../etc/passwd",
                user=self.user,
                session=self.session,
                upload_id="beef",
            )

        self.assertEqual(cm.exception.resource, "/photos/../etc/passwd")
        self.bucket_load.assert_not_awaited()
        self.rmtree.assert_not_awaited()
