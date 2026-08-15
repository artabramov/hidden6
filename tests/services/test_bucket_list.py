# tests/services/test_bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.hooks import Events  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.bucket_list import bucket_list  # noqa: E402

load_all_models()


class TestBucketList(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = MagicMock()

    async def test_non_root_lists_own_buckets_only(self):
        user = User(id=1, username="alice", is_root=False)
        buckets = [Bucket(user_id=1, bucket_name="photos")]
        repo = MagicMock()
        repo.select_all = AsyncMock(return_value=buckets)

        with (
            patch(
                "app.services.bucket_list.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_list.hooks.emit",
                new_callable=AsyncMock,
            ) as emit_mock,
        ):
            result = await bucket_list(session=self.session, current_user=user)

        repo.select_all.assert_awaited_once_with(
            Bucket,
            order_by="bucket_name",
            order="asc",
            user_id=1,
        )
        self.assertEqual(result, buckets)
        emit_mock.assert_awaited_once_with(Events.BUCKET_LISTED, buckets)

    async def test_root_lists_all_buckets(self):
        user = User(id=1, username="root", is_root=True)
        buckets = [
            Bucket(user_id=1, bucket_name="a"),
            Bucket(user_id=2, bucket_name="b"),
        ]
        repo = MagicMock()
        repo.select_all = AsyncMock(return_value=buckets)

        with (
            patch(
                "app.services.bucket_list.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_list.hooks.emit",
                new_callable=AsyncMock,
            ) as emit_mock,
        ):
            result = await bucket_list(session=self.session, current_user=user)

        repo.select_all.assert_awaited_once_with(
            Bucket,
            order_by="bucket_name",
            order="asc",
        )
        self.assertEqual(result, buckets)
        emit_mock.assert_awaited_once_with(Events.BUCKET_LISTED, buckets)

    async def test_returns_empty_list(self):
        user = User(id=1, username="alice", is_root=False)
        repo = MagicMock()
        repo.select_all = AsyncMock(return_value=[])

        with (
            patch(
                "app.services.bucket_list.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_list.hooks.emit",
                new_callable=AsyncMock,
            ) as emit_mock,
        ):
            result = await bucket_list(session=self.session, current_user=user)

        self.assertEqual(result, [])
        emit_mock.assert_awaited_once_with(Events.BUCKET_LISTED, [])
