# tests/routers/test_bucket_create.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import S3InvalidBucketNameError  # noqa: E402
from app.routers.bucket_create import bucket_create_router  # noqa: E402


class TestBucketCreateRouter(unittest.IsolatedAsyncioTestCase):
    async def test_returns_200_with_location(self):
        user = MagicMock()
        session = MagicMock()
        bucket = MagicMock()

        with patch(
            "app.routers.bucket_create.bucket_create",
            new_callable=AsyncMock,
            return_value=bucket,
        ) as mock_service:
            response = await bucket_create_router(
                bucket_name="photos",
                user=user,
                session=session,
            )

        mock_service.assert_awaited_once_with(
            bucket_name="photos",
            user=user,
            session=session,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers["Location"], "/photos")

    async def test_invalid_name_raises_s3_error(self):
        with self.assertRaises(S3InvalidBucketNameError) as cm:
            await bucket_create_router(
                bucket_name="Bad_Name",
                user=MagicMock(),
                session=MagicMock(),
            )

        self.assertEqual(cm.exception.resource, "/Bad_Name")
        self.assertEqual(cm.exception.status_code, 400)
