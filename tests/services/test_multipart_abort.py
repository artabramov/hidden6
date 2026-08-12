# tests/services/test_multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3ObjektUploadNotFoundError  # noqa: E402
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

        self.repo = MagicMock()
        self.repo.delete = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self.multipart_load = self._patch(
            "multipart_load",
            new_callable=AsyncMock,
            return_value=self.multipart,
        )
        self.multipart_cleanup = self._patch(
            "multipart_cleanup",
            new_callable=AsyncMock,
        )

    async def _abort(self):
        await multipart_abort(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
            upload_id="beef",
        )

    async def test_drops_upload_and_staged_parts(self):
        await self._abort()

        self.repo.delete.assert_awaited_once_with(
            self.multipart,
            commit=True,
        )
        self.multipart_cleanup.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_unknown_upload_raises(self):
        self.multipart_load.side_effect = S3ObjektUploadNotFoundError()

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._abort()

        self.repo.delete.assert_not_awaited()
        self.multipart_cleanup.assert_not_awaited()
