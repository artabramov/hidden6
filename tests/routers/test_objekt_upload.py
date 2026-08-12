# tests/routers/test_objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import (  # noqa: E402
    S3ObjektKeyInvalidError,
    S3ObjektTooLargeError,
)
from app.routers.objekt_upload import objekt_upload_router  # noqa: E402
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
            "app.routers.objekt_upload.objekt_upload",
            new_callable=AsyncMock,
            return_value=objekt,
        ) as mock_service:
            response = await objekt_upload_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=self._build_request(),
                user=user,
                session=session,
            )

        kwargs = mock_service.await_args.kwargs
        self.assertEqual(kwargs["bucket_name"], "photos")
        self.assertEqual(kwargs["object_key"], "2024/cat.png")
        self.assertIs(kwargs["user"], user)
        self.assertIs(kwargs["session"], session)
        self.assertIsInstance(kwargs["body"], RequestBodyReader)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.headers["ETag"],
            '"d41d8cd98f00b204e9800998ecf8427e"',
        )

    async def test_invalid_key_raises_s3_error(self):
        with self.assertRaises(S3ObjektKeyInvalidError) as cm:
            await objekt_upload_router(
                bucket_name="photos",
                object_key="../etc/passwd",
                request=self._build_request(),
                user=MagicMock(),
                session=MagicMock(),
            )

        self.assertEqual(cm.exception.resource, "/photos/../etc/passwd")
        self.assertEqual(cm.exception.status_code, 400)

    async def test_oversized_content_length_raises_s3_error(self):
        request = self._build_request({"content-length": "99999999999999"})

        with self.assertRaises(S3ObjektTooLargeError) as cm:
            await objekt_upload_router(
                bucket_name="photos",
                object_key="cat.png",
                request=request,
                user=MagicMock(),
                session=MagicMock(),
            )

        self.assertEqual(cm.exception.resource, "/photos/cat.png")
