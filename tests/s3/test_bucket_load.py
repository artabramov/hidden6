# tests/s3/test_bucket_load.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3AccessDeniedError,
    S3BucketNotFoundError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.s3.bucket_load import bucket_load  # noqa: E402

load_all_models()


class TestBucketLoad(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.root = User(id=2, username="root", is_root=True)

    def _build_repo(self, bucket):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=bucket)
        return repo

    async def test_returns_own_bucket(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")

        result = await bucket_load(
            self._build_repo(bucket),
            "photos",
            self.user,
            "/photos",
        )

        self.assertIs(result, bucket)

    async def test_returns_foreign_bucket_for_root(self):
        bucket = Bucket(id=7, user_id=99, bucket_name="photos")

        result = await bucket_load(
            self._build_repo(bucket),
            "photos",
            self.root,
            "/photos",
        )

        self.assertIs(result, bucket)

    async def test_missing_bucket_raises(self):
        with self.assertRaises(S3BucketNotFoundError):
            await bucket_load(
                self._build_repo(None),
                "photos",
                self.user,
                "/photos",
            )

    async def test_foreign_bucket_is_denied(self):
        bucket = Bucket(id=7, user_id=99, bucket_name="photos")

        with self.assertRaises(S3AccessDeniedError):
            await bucket_load(
                self._build_repo(bucket),
                "photos",
                self.user,
                "/photos",
            )
