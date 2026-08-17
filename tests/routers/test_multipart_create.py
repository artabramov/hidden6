# tests/routers/test_multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import (  # noqa: E402
    S3NotImplementedError,
    S3XmlMalformedError,
)
from app.routers.multipart_create import (  # noqa: E402
    multipart_create_router,
)

COMPLETE_XML = (
    b"<CompleteMultipartUpload>"
    b"<Part><PartNumber>1</PartNumber><ETag>aaa</ETag></Part>"
    b"</CompleteMultipartUpload>"
)


class TestMultipartCreateRouter(unittest.IsolatedAsyncioTestCase):
    def _build_request(self, body=b""):
        request = MagicMock()
        request.headers = {}
        request.body = AsyncMock(return_value=body)
        return request

    async def test_creates_upload(self):
        multipart = MagicMock()
        multipart.upload_id = "beef"
        user = MagicMock()
        session = MagicMock()

        with patch(
            "app.routers.multipart_create.multipart_create",
            new_callable=AsyncMock,
            return_value=multipart,
        ) as mock_service:
            response = await multipart_create_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=self._build_request(),
                session=session,
                current_user=user,
                uploads="",
            )

        mock_service.assert_awaited_once_with(
            session=session,
            current_user=user,
            bucket_name="photos",
            objekt_key="2024/cat.png",
            content_type=None,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "application/xml")
        self.assertIn(b"<UploadId>beef</UploadId>", response.body)

    async def test_passes_content_type_header(self):
        multipart = MagicMock()
        multipart.upload_id = "beef"
        request = self._build_request()
        request.headers = {"content-type": "image/png"}

        with patch(
            "app.routers.multipart_create.multipart_create",
            new_callable=AsyncMock,
            return_value=multipart,
        ) as mock_service:
            await multipart_create_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=request,
                session=MagicMock(),
                current_user=MagicMock(),
                uploads="",
            )

        self.assertEqual(
            mock_service.await_args.kwargs["content_type"],
            "image/png",
        )

    async def test_completes_upload(self):
        objekt = MagicMock()
        objekt.etag = "abc-1"
        session = MagicMock()
        user = MagicMock()

        with patch(
            "app.routers.multipart_create.multipart_complete",
            new_callable=AsyncMock,
            return_value=objekt,
        ) as mock_service:
            response = await multipart_create_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=self._build_request(COMPLETE_XML),
                session=session,
                current_user=user,
                upload_id="beef",
            )

        kwargs = mock_service.await_args.kwargs
        self.assertIs(kwargs["session"], session)
        self.assertIs(kwargs["current_user"], user)
        self.assertEqual(kwargs["bucket_name"], "photos")
        self.assertEqual(kwargs["objekt_key"], "2024/cat.png")
        self.assertEqual(kwargs["upload_id"], "beef")
        self.assertEqual(kwargs["parts"][0].part_number, 1)
        self.assertEqual(kwargs["parts"][0].etag, "aaa")
        self.assertIn(b'<ETag>"abc-1"</ETag>', response.body)

    async def test_malformed_body_raises_s3_error(self):
        with self.assertRaises(S3XmlMalformedError) as cm:
            await multipart_create_router(
                bucket_name="photos",
                object_key="cat.png",
                request=self._build_request(b"<nope"),
                session=MagicMock(),
                current_user=MagicMock(),
                upload_id="beef",
            )

        self.assertEqual(cm.exception.resource, "/photos/cat.png")

    async def test_post_without_multipart_query_is_not_implemented(self):
        with self.assertRaises(S3NotImplementedError) as cm:
            await multipart_create_router(
                bucket_name="photos",
                object_key="cat.png",
                request=self._build_request(),
                session=MagicMock(),
                current_user=MagicMock(),
            )

        self.assertEqual(cm.exception.status_code, 501)
