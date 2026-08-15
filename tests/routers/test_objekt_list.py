# tests/routers/test_objekt_list.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.routers.objekt_list import objekt_list_router  # noqa: E402

load_all_models()


class TestObjektListRouter(unittest.IsolatedAsyncioTestCase):
    async def test_returns_200_with_list_bucket_xml(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()
        objekts = [
            Objekt(
                id=3,
                bucket_id=7,
                user_id=1,
                object_key="2024/cat.png",
                size_bytes=12,
                etag="etag123",
                content_type="image/png",
                created_at=1_704_067_200,
                modified_at=1_704_067_200,
            ),
        ]

        with patch(
            "app.routers.objekt_list.objekt_list",
            new_callable=AsyncMock,
            return_value=objekts,
        ) as mock_service:
            response = await objekt_list_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                prefix="2024/",
                max_keys=100,
            )

        mock_service.assert_awaited_once_with(
            bucket_name="photos",
            user=user,
            session=session,
            prefix="2024/",
            max_keys=100,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "application/xml")

        body = response.body.decode()
        self.assertIn("<ListBucketResult", body)
        self.assertIn("<Name>photos</Name>", body)
        self.assertIn("<Prefix>2024/</Prefix>", body)
        self.assertIn("<MaxKeys>100</MaxKeys>", body)
        self.assertIn("<Key>2024/cat.png</Key>", body)
        self.assertIn("<ETag>&quot;etag123&quot;</ETag>", body)

    async def test_returns_empty_contents_xml(self):
        user = User(id=2, username="bob", is_root=False)
        session = MagicMock()

        with patch(
            "app.routers.objekt_list.objekt_list",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_service:
            response = await objekt_list_router(
                bucket_name="photos",
                session=session,
                current_user=user,
            )

        mock_service.assert_awaited_once_with(
            bucket_name="photos",
            user=user,
            session=session,
            prefix="",
            max_keys=1000,
        )
        body = response.body.decode()
        self.assertIn("<KeyCount>0</KeyCount>", body)
        self.assertNotIn("<Contents>", body)
