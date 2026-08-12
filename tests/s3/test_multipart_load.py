# tests/s3/test_multipart_load.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3ObjektUploadNotFoundError  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.s3.multipart_load import multipart_load  # noqa: E402

load_all_models()


class TestMultipartLoad(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
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

    async def _load(self):
        return await multipart_load(
            repo=self.repo,
            bucket=self.bucket,
            object_key="2024/cat.png",
            upload_id="beef",
            resource="/photos/2024/cat.png",
        )

    async def test_returns_upload_of_the_addressed_key(self):
        multipart = await self._load()

        self.assertIs(multipart, self.multipart)

    async def test_unknown_upload_raises(self):
        self.repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._load()

    async def test_upload_of_another_bucket_raises(self):
        self.multipart.bucket_id = 99

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._load()

    async def test_upload_of_another_key_raises(self):
        self.multipart.object_key = "other.png"

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._load()
