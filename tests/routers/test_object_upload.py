# tests/routers/test_object_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import (  # noqa: E402
    S3ObjectPartNumberInvalidError,
    S3ObjectTooLargeError,
)
from app.routers.object_upload import object_upload_router  # noqa: E402
from app.streams import RequestBodyReader  # noqa: E402


class TestObjektUploadRouter(unittest.IsolatedAsyncioTestCase):
    def _build_request(self, headers=None):
        request = MagicMock()
        request.headers = headers or {}
        return request

    async def test_returns_200_with_etag(self):
        objekt = MagicMock()
        objekt.etag = "d41d8cd98f00b204e9800998ecf8427e"
        user = MagicMock()
        session = MagicMock()

        with patch(
            "app.routers.object_upload.object_upload",
            new_callable=AsyncMock,
            return_value=objekt,
        ) as mock_service:
            response = await object_upload_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=self._build_request(),
                session=session,
                current_user=user,
            )

        kwargs = mock_service.await_args.kwargs
        self.assertIs(kwargs["session"], session)
        self.assertIs(kwargs["current_user"], user)
        self.assertEqual(kwargs["bucket_name"], "photos")
        self.assertEqual(kwargs["object_key"], "2024/cat.png")
        self.assertIsInstance(kwargs["body"], RequestBodyReader)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.headers["ETag"],
            '"d41d8cd98f00b204e9800998ecf8427e"',
        )

    async def test_uploads_part_when_upload_id_is_given(self):
        user = MagicMock()
        session = MagicMock()

        with patch(
            "app.routers.object_upload.multipart_upload",
            new_callable=AsyncMock,
            return_value="9b2cf5",
        ) as mock_service:
            response = await object_upload_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=self._build_request(),
                session=session,
                current_user=user,
                upload_id="beef",
                part_number=2,
            )

        kwargs = mock_service.await_args.kwargs
        self.assertIs(kwargs["session"], session)
        self.assertIs(kwargs["current_user"], user)
        self.assertEqual(kwargs["bucket_name"], "photos")
        self.assertEqual(kwargs["object_key"], "2024/cat.png")
        self.assertEqual(kwargs["upload_id"], "beef")
        self.assertEqual(kwargs["part_number"], 2)
        self.assertIsInstance(kwargs["body"], RequestBodyReader)
        self.assertEqual(response.headers["ETag"], '"9b2cf5"')

    async def test_part_without_number_raises_s3_error(self):
        with self.assertRaises(S3ObjectPartNumberInvalidError) as cm:
            await object_upload_router(
                bucket_name="photos",
                object_key="cat.png",
                request=self._build_request(),
                session=MagicMock(),
                current_user=MagicMock(),
                upload_id="beef",
            )

        self.assertEqual(cm.exception.resource, "/photos/cat.png")

    async def test_oversized_content_length_raises_s3_error(self):
        request = self._build_request({"content-length": "99999999999999"})

        with self.assertRaises(S3ObjectTooLargeError) as cm:
            await object_upload_router(
                bucket_name="photos",
                object_key="cat.png",
                request=request,
                session=MagicMock(),
                current_user=MagicMock(),
            )

        self.assertEqual(cm.exception.resource, "/photos/cat.png")
