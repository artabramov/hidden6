# tests/routers/test_objekt_download.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status
from fastapi.responses import StreamingResponse

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.routers.objekt_download import objekt_download_router  # noqa: E402
from app.s3.datetime import datetime_http  # noqa: E402

load_all_models()


class TestObjektDownloadRouter(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
            created_at=1_704_067_200,
            modified_at=1_704_067_200,
        )
        self.object_path = "/mnt/buckets/photos/2024/cat.png"

    def _request(self, method: str) -> MagicMock:
        request = MagicMock()
        request.method = method
        return request

    async def test_get_streams_object_bytes(self):
        chunks = [b"hello", b" world"]

        async def _iter_read(_path):
            for chunk in chunks:
                yield chunk

        with (
            patch(
                "app.routers.objekt_download.objekt_download",
                new_callable=AsyncMock,
                return_value=(self.objekt, self.object_path),
            ) as mock_service,
            patch(
                "app.routers.objekt_download.iter_read",
                side_effect=_iter_read,
            ) as mock_iter,
        ):
            response = await objekt_download_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=self._request("GET"),
                session=self.session,
                current_user=self.user,
            )

        mock_service.assert_awaited_once_with(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
        )
        mock_iter.assert_called_once_with(self.object_path)
        self.assertIsInstance(response, StreamingResponse)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.headers["Content-Length"], "12")
        self.assertEqual(response.headers["ETag"], '"etag123"')
        self.assertEqual(
            response.headers["Last-Modified"],
            datetime_http(1_704_067_200),
        )

        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        self.assertEqual(body, b"hello world")

    async def test_head_returns_metadata_without_body(self):
        with (
            patch(
                "app.routers.objekt_download.objekt_download",
                new_callable=AsyncMock,
                return_value=(self.objekt, self.object_path),
            ) as mock_service,
            patch(
                "app.routers.objekt_download.iter_read",
            ) as mock_iter,
        ):
            response = await objekt_download_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                request=self._request("HEAD"),
                session=self.session,
                current_user=self.user,
            )

        mock_service.assert_awaited_once_with(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
        )
        mock_iter.assert_not_called()
        self.assertNotIsInstance(response, StreamingResponse)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.headers["Content-Length"], "12")
        self.assertEqual(response.headers["ETag"], '"etag123"')
        self.assertEqual(
            response.headers["Last-Modified"],
            datetime_http(1_704_067_200),
        )
        self.assertEqual(response.body, b"")
