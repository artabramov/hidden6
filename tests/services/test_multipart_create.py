# tests/services/test_multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3BucketNotFoundError  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.multipart_create import multipart_create  # noqa: E402

load_all_models()


class TestMultipartCreate(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(
            f"app.services.multipart_create.{target}",
            **kwargs,
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")

        config = MagicMock()
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        self.repo = MagicMock()
        self.repo.insert = AsyncMock(side_effect=lambda obj, **kw: obj)
        self.repo.rollback = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch("uuid.uuid4", return_value=MagicMock(hex="beef"))
        self.bucket_load = self._patch(
            "bucket_load",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.mktree = self._patch("mktree", new_callable=AsyncMock)
        self.rmtree = self._patch("rmtree", new_callable=AsyncMock)

    async def _create(self):
        return await multipart_create(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
        )

    async def test_registers_upload_and_stages_dir(self):
        multipart = await self._create()

        self.mktree.assert_awaited_once_with("/mnt/tmp/beef")
        self.repo.insert.assert_awaited_once()
        self.assertEqual(multipart.upload_id, "beef")
        self.assertEqual(multipart.bucket_id, 7)
        self.assertEqual(multipart.user_id, 1)
        self.assertEqual(multipart.object_key, "2024/cat.png")
        self.assertEqual(
            self.repo.insert.await_args.kwargs["commit"],
            True,
        )

    async def test_inaccessible_bucket_stops_before_staging(self):
        self.bucket_load.side_effect = S3BucketNotFoundError("/photos")

        with self.assertRaises(S3BucketNotFoundError):
            await self._create()

        self.mktree.assert_not_awaited()

    async def test_failed_insert_removes_staged_dir(self):
        self.repo.insert.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._create()

        self.repo.rollback.assert_awaited_once()
        self.rmtree.assert_awaited_once_with("/mnt/tmp/beef")
