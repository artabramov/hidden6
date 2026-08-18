# tests/routers/test_bucket_put.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.routers.bucket_put import bucket_put_router  # noqa: E402

VERSIONING_BODY = (
    b"<VersioningConfiguration>"
    b"<Status>Enabled</Status>"
    b"</VersioningConfiguration>"
)


class TestBucketPutRouter(unittest.IsolatedAsyncioTestCase):
    def _build_request(self, body=b""):
        request = MagicMock()
        request.body = AsyncMock(return_value=body)
        return request

    async def test_returns_200_with_location(self):
        user = MagicMock()
        session = MagicMock()
        bucket = MagicMock()

        with (
            patch(
                "app.routers.bucket_put.bucket_create",
                new_callable=AsyncMock,
                return_value=bucket,
            ) as mock_create,
            patch(
                "app.routers.bucket_put.bucket_versioning_update",
                new_callable=AsyncMock,
            ) as mock_versioning,
        ):
            response = await bucket_put_router(
                bucket_name="photos",
                request=self._build_request(),
                session=session,
                current_user=user,
            )

        mock_create.assert_awaited_once_with(
            session=session,
            current_user=user,
            bucket_name="photos",
        )
        mock_versioning.assert_not_awaited()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers["Location"], "/photos")

    async def test_applies_versioning_configuration(self):
        user = MagicMock()
        session = MagicMock()

        with (
            patch(
                "app.routers.bucket_put.bucket_versioning_update",
                new_callable=AsyncMock,
            ) as mock_versioning,
            patch(
                "app.routers.bucket_put.bucket_create",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            response = await bucket_put_router(
                bucket_name="photos",
                request=self._build_request(VERSIONING_BODY),
                session=session,
                current_user=user,
                versioning="",
            )

        mock_versioning.assert_awaited_once_with(
            session=session,
            current_user=user,
            bucket_name="photos",
            body=VERSIONING_BODY,
        )
        mock_create.assert_not_awaited()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("Location", response.headers)
