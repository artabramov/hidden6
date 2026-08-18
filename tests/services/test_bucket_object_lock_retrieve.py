# tests/services/test_bucket_object_lock_retrieve.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import BUCKET_VERSIONING_ENABLED  # noqa: E402
from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3ObjectLockConfigurationNotFoundError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.bucket_object_lock_retrieve import (  # noqa: E402
    bucket_object_lock_retrieve,
)

load_all_models()


class TestBucketObjectLockRetrieve(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = MagicMock()
        self.user = User(id=1, username="alice", is_root=False)

    def _bucket(self, *, object_lock_enabled: bool) -> Bucket:
        return Bucket(
            id=7,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=object_lock_enabled,
        )

    async def test_returns_bucket_when_object_lock_enabled(self):
        bucket = self._bucket(object_lock_enabled=True)
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_object_lock_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_retrieve.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ) as load_bucket_mock,
        ):
            result = await bucket_object_lock_retrieve(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
            )

        self.assertIs(result, bucket)
        load_bucket_mock.assert_awaited_once_with(
            repo,
            "photos",
            self.user,
            "/photos",
        )

    async def test_raises_when_object_lock_disabled(self):
        bucket = self._bucket(object_lock_enabled=False)
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_object_lock_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_retrieve.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(
                S3ObjectLockConfigurationNotFoundError,
            ) as cm:
                await bucket_object_lock_retrieve(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        self.assertEqual(cm.exception.resource, "/photos")

    async def test_bucket_not_found_raises(self):
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_object_lock_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_retrieve.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3BucketNotFoundError("/photos"),
            ),
        ):
            with self.assertRaises(S3BucketNotFoundError):
                await bucket_object_lock_retrieve(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

    async def test_access_denied_raises(self):
        other_user = User(id=99, username="eve", is_root=False)
        repo = MagicMock()

        with (
            patch(
                "app.services.bucket_object_lock_retrieve.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_retrieve.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3AccessDeniedError("/photos"),
            ),
        ):
            with self.assertRaises(S3AccessDeniedError):
                await bucket_object_lock_retrieve(
                    session=self.session,
                    current_user=other_user,
                    bucket_name="photos",
                )
