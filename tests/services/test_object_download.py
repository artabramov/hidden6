# tests/services/test_object_download.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3BucketNotFoundError,
    S3ObjectKeyInvalidError,
    S3ObjectNotFoundError,
)
from app.hooks import Events  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.object import S3Object  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.object_download import object_download  # noqa: E402

load_all_models()


class TestObjectDownload(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.s3_object = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
            created_at=1_704_067_200,
        )

    def _patch(self, target, **kwargs):
        patcher = patch(f"app.services.object_download.{target}", **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _build_mocks(self, isfile=True):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        self._patch("get_config", return_value=config)

        repo = MagicMock()
        self._patch("ORMRepository", return_value=repo)

        self.load_bucket = self._patch(
            "load_bucket",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.load_object = self._patch(
            "load_object",
            new_callable=AsyncMock,
            return_value=self.s3_object,
        )
        self.isfile = self._patch(
            "isfile",
            new_callable=AsyncMock,
            return_value=isfile,
        )
        self.emit = self._patch(
            "hooks.emit",
            new_callable=AsyncMock,
        )
        return repo

    async def test_returns_object_and_path(self):
        self._build_mocks()

        s3_object, path = await object_download(
            session=self.session,
            current_user=self.user,
            bucket_name="photos",
            object_key="2024/cat.png",
        )

        self.assertIs(s3_object, self.s3_object)
        self.assertEqual(path, "/mnt/buckets/photos/2024/cat.png")
        self.load_bucket.assert_awaited_once()
        self.load_object.assert_awaited_once()
        self.isfile.assert_awaited_once_with("/mnt/buckets/photos/2024/cat.png")
        self.emit.assert_awaited_once_with(
            Events.OBJECT_DOWNLOADED,
            self.s3_object,
        )

    async def test_invalid_key_stops_before_storage(self):
        self._build_mocks()

        with self.assertRaises(S3ObjectKeyInvalidError):
            await object_download(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                object_key="../escape",
            )

        self.load_bucket.assert_not_awaited()
        self.load_object.assert_not_awaited()

    async def test_missing_bucket_raises(self):
        self._build_mocks()
        self.load_bucket.side_effect = S3BucketNotFoundError("/photos/x")

        with self.assertRaises(S3BucketNotFoundError):
            await object_download(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                object_key="2024/cat.png",
            )

        self.load_object.assert_not_awaited()

    async def test_missing_object_raises(self):
        self._build_mocks()
        self.load_object.side_effect = S3ObjectNotFoundError(
            "/photos/2024/cat.png",
        )

        with self.assertRaises(S3ObjectNotFoundError):
            await object_download(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                object_key="2024/cat.png",
            )

        self.isfile.assert_not_awaited()
        self.emit.assert_not_awaited()

    async def test_missing_file_on_disk_raises(self):
        self._build_mocks(isfile=False)

        with self.assertRaises(S3ObjectNotFoundError):
            await object_download(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                object_key="2024/cat.png",
            )

        self.emit.assert_not_awaited()
