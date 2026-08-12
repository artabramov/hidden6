# tests/services/test_multipart_store.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3ObjektUploadNotFoundError  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.multipart_store import (  # noqa: E402
    load_multipart,
    part_path,
    remove_upload_dir,
    upload_dir,
)

load_all_models()


class TestLoadMultipart(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )
        self.repo = MagicMock()
        self.repo.select = AsyncMock(return_value=self.multipart)

    async def _load(self, bucket=None):
        return await load_multipart(
            repo=self.repo,
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            upload_id="beef",
            resource="/photos/2024/cat.png",
            bucket=bucket,
        )

    async def test_returns_upload_of_the_addressed_key(self):
        multipart = await self._load(bucket=self.bucket)

        self.assertIs(multipart, self.multipart)

    async def test_loads_bucket_when_not_given(self):
        with patch(
            "app.services.multipart_store.load_bucket",
            new_callable=AsyncMock,
            return_value=self.bucket,
        ) as load_bucket_mock:
            multipart = await self._load()

        load_bucket_mock.assert_awaited_once()
        self.assertIs(multipart, self.multipart)

    async def test_unknown_upload_raises(self):
        self.repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._load(bucket=self.bucket)

    async def test_upload_of_another_bucket_raises(self):
        self.multipart.bucket_id = 99

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._load(bucket=self.bucket)

    async def test_upload_of_another_key_raises(self):
        self.multipart.object_key = "other.png"

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._load(bucket=self.bucket)


class TestStagedPaths(unittest.TestCase):
    def test_upload_dir_is_named_after_the_upload(self):
        self.assertEqual(upload_dir("/mnt/tmp", "beef"), "/mnt/tmp/beef")

    def test_part_path_is_padded(self):
        self.assertEqual(
            part_path("/mnt/tmp/beef", 42),
            "/mnt/tmp/beef/part.00042",
        )


class TestRemoveUploadDir(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(
            f"app.services.multipart_store.{target}",
            **kwargs,
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.log = self._patch("log")
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.listdir = self._patch(
            "listdir",
            new_callable=AsyncMock,
            return_value=["part.00001", "part.00002"],
        )
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.rmdir = self._patch("rmdir", new_callable=AsyncMock)

    async def test_removes_parts_and_directory(self):
        await remove_upload_dir("/mnt/tmp/beef")

        self.assertEqual(
            [call.args[0] for call in self.delete.await_args_list],
            ["/mnt/tmp/beef/part.00001", "/mnt/tmp/beef/part.00002"],
        )
        self.rmdir.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_missing_directory_is_skipped(self):
        self.isdir.return_value = False

        await remove_upload_dir("/mnt/tmp/beef")

        self.delete.assert_not_awaited()
        self.rmdir.assert_not_awaited()

    async def test_failed_cleanup_is_logged(self):
        self.rmdir.side_effect = OSError("busy")

        await remove_upload_dir("/mnt/tmp/beef")

        self.log.exception.assert_called_once()
