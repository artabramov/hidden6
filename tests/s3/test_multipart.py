# tests/s3/test_multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjektPartInvalidError,
    S3ObjektPartNumberInvalidError,
    S3ObjektPartOrderInvalidError,
    S3ObjektPartTooSmallError,
    S3ObjektUploadNotFoundError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.s3.multipart import multipart_load, multipart_parts  # noqa: E402
from app.schemas.multipart_complete import MultipartPart  # noqa: E402

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


class TestMultipartParts(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(f"app.s3.multipart.{target}", **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.isfile = self._patch(
            "isfile",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.get_filesize = self._patch(
            "get_filesize",
            new_callable=AsyncMock,
            return_value=1024 * 1024 * 6,
        )

    def _build_parts(self, numbers):
        return [
            MultipartPart(part_number=number, etag="aaa")
            for number in numbers
        ]

    async def _resolve(self, numbers=(1, 2)):
        return await multipart_parts(
            "/mnt/tmp/beef",
            self._build_parts(numbers),
            "/photos/2024/cat.png",
        )

    async def test_maps_parts_onto_staged_files(self):
        paths = await self._resolve()

        self.assertEqual(
            paths,
            ["/mnt/tmp/beef/1.part", "/mnt/tmp/beef/2.part"],
        )

    async def test_rejects_unordered_parts(self):
        with self.assertRaises(S3ObjektPartOrderInvalidError):
            await self._resolve(numbers=(2, 1))

    async def test_rejects_repeated_part(self):
        with self.assertRaises(S3ObjektPartOrderInvalidError):
            await self._resolve(numbers=(1, 1))

    async def test_rejects_part_number_above_maximum(self):
        with self.assertRaises(S3ObjektPartNumberInvalidError):
            await self._resolve(numbers=(10001,))

    async def test_rejects_missing_part(self):
        self.isfile.return_value = False

        with self.assertRaises(S3ObjektPartInvalidError):
            await self._resolve()

    async def test_rejects_small_leading_part(self):
        self.get_filesize.return_value = 1024

        with self.assertRaises(S3ObjektPartTooSmallError):
            await self._resolve()

    async def test_last_part_may_be_small(self):
        self.get_filesize.return_value = 1024

        paths = await self._resolve(numbers=(1,))

        self.assertEqual(paths, ["/mnt/tmp/beef/1.part"])
