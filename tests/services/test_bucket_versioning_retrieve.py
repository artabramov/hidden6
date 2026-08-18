# tests/services/test_bucket_versioning_retrieve.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import (  # noqa: E402
    BUCKET_VERSIONING_DISABLED,
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
)
from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3AccessDeniedError, S3BucketNotFoundError  # noqa: E402
from app.models.bucket import S3Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.bucket_versioning_retrieve import bucket_versioning_retrieve  # noqa: E402

load_all_models()


class TestBucketVersioningRetrieve(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = MagicMock()
        self.user = User(id=1, username="alice", is_root=False)

    def _bucket(self, versioning_status: str) -> S3Bucket:
        return S3Bucket(
            id=7,
            user_id=1,
            bucket_name="photos",
            versioning_status=versioning_status,
        )

    async def test_disabled_returns_none(self):
        bucket = self._bucket(BUCKET_VERSIONING_DISABLED)
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_versioning_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_retrieve.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ) as load_bucket_mock,
        ):
            result = await bucket_versioning_retrieve(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
            )

        self.assertIsNone(result)
        load_bucket_mock.assert_awaited_once_with(
            repo,
            "photos",
            self.user,
            "/photos",
        )

    async def test_enabled_returns_status(self):
        bucket = self._bucket(BUCKET_VERSIONING_ENABLED)
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_versioning_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_retrieve.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            result = await bucket_versioning_retrieve(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
            )

        self.assertEqual(result, BUCKET_VERSIONING_ENABLED)

    async def test_suspended_returns_status(self):
        bucket = self._bucket(BUCKET_VERSIONING_SUSPENDED)
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_versioning_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_retrieve.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            result = await bucket_versioning_retrieve(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
            )

        self.assertEqual(result, BUCKET_VERSIONING_SUSPENDED)

    async def test_bucket_not_found_raises(self):
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_versioning_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_retrieve.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3BucketNotFoundError("/photos"),
            ),
        ):
            with self.assertRaises(S3BucketNotFoundError):
                await bucket_versioning_retrieve(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

    async def test_access_denied_raises(self):
        other_user = User(id=99, username="eve", is_root=False)
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_versioning_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_retrieve.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3AccessDeniedError("/photos"),
            ),
        ):
            with self.assertRaises(S3AccessDeniedError):
                await bucket_versioning_retrieve(
                    session=self.session,
                    current_user=other_user,
                    bucket_name="photos",
                )
