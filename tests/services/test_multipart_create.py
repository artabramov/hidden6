# tests/services/test_multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT  # noqa: E402
from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3BucketNotFoundError,
    S3ObjectKeyInvalidError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.multipart_create import multipart_create  # noqa: E402

load_all_models()

UPLOAD_PATH = "/mnt/tmp/beef"


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
        self.log = self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")

        config = MagicMock()
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        self.repo = MagicMock()
        self.repo.insert = AsyncMock(side_effect=lambda obj, **kw: obj)
        self.repo.commit = AsyncMock()
        self.repo.rollback = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch("uuid.uuid4", return_value=MagicMock(hex="beef"))
        self.load_bucket = self._patch(
            "load_bucket",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.mktree = self._patch("mktree", new_callable=AsyncMock)
        self.rmtree = self._patch("rmtree", new_callable=AsyncMock)

    async def _create(self, content_type=None):
        return await multipart_create(
            session=self.session,
            current_user=self.user,
            bucket_name="photos",
            objekt_key="2024/cat.png",
            content_type=content_type,
        )

    async def test_registers_upload_and_stages_dir(self):
        multipart = await self._create()

        self.mktree.assert_awaited_once_with(UPLOAD_PATH)
        self.repo.insert.assert_awaited_once()
        inserted = self.repo.insert.await_args.args[0]
        self.assertIs(inserted, multipart)
        self.assertNotIn("commit", self.repo.insert.await_args.kwargs)
        self.repo.commit.assert_awaited_once()
        self.rmtree.assert_not_awaited()
        self.assertEqual(multipart.upload_id, "beef")
        self.assertEqual(multipart.bucket_id, 7)
        self.assertEqual(multipart.user_id, 1)
        self.assertEqual(multipart.object_key, "2024/cat.png")
        self.assertEqual(multipart.content_type, OBJEKT_CONTENT_TYPE_DEFAULT)

    async def test_stores_supplied_content_type(self):
        multipart = await self._create(content_type="image/png")

        self.assertEqual(multipart.content_type, "image/png")

    async def test_inaccessible_bucket_stops_before_staging(self):
        self.load_bucket.side_effect = S3BucketNotFoundError("/photos")

        with self.assertRaises(S3BucketNotFoundError):
            await self._create()

        self.mktree.assert_not_awaited()
        self.repo.insert.assert_not_awaited()
        self.rmtree.assert_not_awaited()

    async def test_invalid_key_stops_before_storage(self):
        with self.assertRaises(S3ObjectKeyInvalidError) as cm:
            await multipart_create(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                objekt_key="../etc/passwd",
            )

        self.assertEqual(cm.exception.resource, "/photos/../etc/passwd")
        self.load_bucket.assert_not_awaited()
        self.mktree.assert_not_awaited()

    async def test_failed_mktree_removes_upload_dir(self):
        self.mktree.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            await self._create()

        self.repo.insert.assert_not_awaited()
        self.repo.commit.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.rmtree.assert_awaited_once_with(UPLOAD_PATH)

    async def test_failed_insert_removes_upload_dir(self):
        self.repo.insert.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._create()

        self.repo.commit.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.rmtree.assert_awaited_once_with(UPLOAD_PATH)

    async def test_failed_commit_removes_upload_dir(self):
        self.repo.commit.side_effect = RuntimeError("commit failed")

        with self.assertRaises(RuntimeError):
            await self._create()

        self.repo.insert.assert_awaited_once()
        self.repo.rollback.assert_awaited_once()
        self.rmtree.assert_awaited_once_with(UPLOAD_PATH)

    async def test_logs_when_rollback_fails(self):
        self.repo.insert.side_effect = RuntimeError("db down")
        self.repo.rollback.side_effect = RuntimeError("session closed")

        with self.assertRaises(RuntimeError) as cm:
            await self._create()

        self.assertEqual(str(cm.exception), "db down")
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args_list[0].args[0],
        )
        self.rmtree.assert_awaited_once_with(UPLOAD_PATH)

    async def test_logs_when_cleanup_fails(self):
        self.repo.insert.side_effect = RuntimeError("db down")
        self.rmtree.side_effect = OSError("busy")

        with self.assertRaises(RuntimeError) as cm:
            await self._create()

        self.assertEqual(str(cm.exception), "db down")
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "upload_path=%s",
            self.log.exception.call_args.args[0],
        )
