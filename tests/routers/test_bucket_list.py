# tests/routers/test_bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.routers.bucket_list import bucket_list_router  # noqa: E402

load_all_models()


class TestBucketListRouter(unittest.IsolatedAsyncioTestCase):
    async def test_returns_200_with_list_buckets_xml(self):
        user = User(id=1, username="root", is_root=True)
        session = MagicMock()
        buckets = [
            Bucket(
                user_id=1,
                bucket_name="my-bucket",
                created_at=1_704_067_200,
            ),
        ]

        with patch(
            "app.routers.bucket_list.bucket_list",
            new_callable=AsyncMock,
            return_value=buckets,
        ) as mock_service:
            response = await bucket_list_router(
                session=session,
                current_user=user,
            )

        mock_service.assert_awaited_once_with(
            session=session,
            current_user=user,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "application/xml")

        body = response.body.decode()
        self.assertIn("<ListAllMyBucketsResult", body)
        self.assertIn("<Name>my-bucket</Name>", body)
        self.assertIn("<DisplayName>root</DisplayName>", body)

    async def test_returns_empty_buckets_xml(self):
        user = User(id=2, username="alice", is_root=False)
        session = MagicMock()

        with patch(
            "app.routers.bucket_list.bucket_list",
            new_callable=AsyncMock,
            return_value=[],
        ):
            response = await bucket_list_router(
                session=session,
                current_user=user,
            )

        body = response.body.decode()
        self.assertIn("<Buckets></Buckets>", body)
        self.assertNotIn("<Bucket>", body)
