# tests/services/test_multipart_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjektPartNumberInvalidError,
    S3ObjektUploadNotFoundError,
)
from app.locks import LockType  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.multipart_upload import multipart_upload  # noqa: E402

load_all_models()

PART_HASH = hashlib.md5(b"first").hexdigest()


class TestMultipartUpload(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(
            f"app.services.multipart_upload.{target}",
            **kwargs,
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )

        config = MagicMock()
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        lock_context = AsyncMock()
        lock_context.__aenter__.return_value = None
        lock_context.__aexit__.return_value = None

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=MagicMock())
        self.bucket_load = self._patch(
            "bucket_load",
            new_callable=AsyncMock,
            return_value=MagicMock(id=7),
        )
        self.multipart_load = self._patch(
            "multipart_load",
            new_callable=AsyncMock,
            return_value=self.multipart,
        )
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.lock = self._patch(
            "locks.lock_file",
            return_value=lock_context,
        )
        self.upload = self._patch("upload", new_callable=AsyncMock)
        self._patch(
            "get_file_hash",
            new_callable=AsyncMock,
            return_value=PART_HASH,
        )

    async def _upload(self, part_number=1):
        return await multipart_upload(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
            upload_id="beef",
            part_number=part_number,
            body=MagicMock(),
        )

    async def test_stores_part_and_returns_etag(self):
        etag = await self._upload()

        part = "/mnt/tmp/beef/1.part"
        self.upload.assert_awaited_once()
        self.assertEqual(self.upload.await_args.args[1], part)
        self.lock.assert_called_once_with(part, LockType.WRITE)
        self.assertEqual(etag, PART_HASH)

    async def test_rejects_part_number_out_of_range(self):
        with self.assertRaises(S3ObjektPartNumberInvalidError):
            await self._upload(part_number=0)

        with self.assertRaises(S3ObjektPartNumberInvalidError):
            await self._upload(part_number=10001)

        self.upload.assert_not_awaited()

    async def test_unknown_upload_raises(self):
        self.multipart_load.side_effect = S3ObjektUploadNotFoundError()

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._upload()

        self.upload.assert_not_awaited()

    async def test_missing_upload_dir_raises(self):
        self.isdir.return_value = False

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._upload()

        self.upload.assert_not_awaited()

    async def test_failed_upload_keeps_the_stored_part(self):
        self.upload.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            await self._upload()
