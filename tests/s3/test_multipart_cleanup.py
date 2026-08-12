# tests/s3/test_multipart_cleanup.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from app.s3.multipart_cleanup import multipart_cleanup


class TestMultipartCleanup(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(f"app.s3.multipart_cleanup.{target}", **kwargs)
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
            return_value=["1.part", "2.part"],
        )
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.rmdir = self._patch("rmdir", new_callable=AsyncMock)

    async def test_removes_parts_and_directory(self):
        await multipart_cleanup("/mnt/tmp/beef")

        self.assertEqual(
            [call.args[0] for call in self.delete.await_args_list],
            ["/mnt/tmp/beef/1.part", "/mnt/tmp/beef/2.part"],
        )
        self.rmdir.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_missing_directory_is_skipped(self):
        self.isdir.return_value = False

        await multipart_cleanup("/mnt/tmp/beef")

        self.delete.assert_not_awaited()
        self.rmdir.assert_not_awaited()

    async def test_failed_cleanup_is_logged(self):
        self.rmdir.side_effect = OSError("busy")

        await multipart_cleanup("/mnt/tmp/beef")

        self.log.exception.assert_called_once()
