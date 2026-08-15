# tests/routers/test_multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import S3NotImplementedError  # noqa: E402
from app.routers.multipart_abort import (  # noqa: E402
    multipart_abort_router,
)


class TestMultipartAbortRouter(unittest.IsolatedAsyncioTestCase):
    async def test_aborts_upload(self):
        user = MagicMock()
        session = MagicMock()

        with patch(
            "app.routers.multipart_abort.multipart_abort",
            new_callable=AsyncMock,
        ) as mock_service:
            response = await multipart_abort_router(
                bucket_name="photos",
                object_key="2024/cat.png",
                session=session,
                current_user=user,
                upload_id="beef",
            )

        mock_service.assert_awaited_once_with(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=user,
            session=session,
            upload_id="beef",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

    async def test_delete_without_upload_id_is_not_implemented(self):
        with self.assertRaises(S3NotImplementedError) as cm:
            await multipart_abort_router(
                bucket_name="photos",
                object_key="cat.png",
                session=MagicMock(),
                current_user=MagicMock(),
            )

        self.assertEqual(cm.exception.status_code, 501)
