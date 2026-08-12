# tests/s3/test_objekt_mkdir.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import S3ObjektKeyConflictError  # noqa: E402
from app.s3.objekt_mkdir import objekt_mkdir  # noqa: E402


class TestObjektMkdir(unittest.IsolatedAsyncioTestCase):
    async def _run(self, isdir_value, mkdir_error=None):
        with (
            patch(
                "app.s3.objekt_mkdir.isdir",
                new_callable=AsyncMock,
                return_value=isdir_value,
            ),
            patch(
                "app.s3.objekt_mkdir.mkdir",
                new_callable=AsyncMock,
                side_effect=mkdir_error,
            ) as mkdir_mock,
        ):
            await objekt_mkdir(
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
