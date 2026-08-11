# tests/handlers/test_s3_error.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock, patch

from app.errors import S3Error
from app.handlers import s3_error_handler


class TestS3ErrorHandler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_xml_error(self):
        request = MagicMock()
        exc = S3Error(
            code="InvalidBucketName",
            message="The specified bucket is not valid.",
            status_code=400,
            resource="/Bad_Name",
        )

        with patch(
            "app.handlers.get_context_var",
            return_value="req-1",
        ):
            response = await s3_error_handler(request, exc)

        body = response.body.decode()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.media_type, "application/xml")
        self.assertIn("<Code>InvalidBucketName</Code>", body)
        self.assertIn(
            "<Message>The specified bucket is not valid.</Message>",
            body,
        )
        self.assertIn("<Resource>/Bad_Name</Resource>", body)
        self.assertIn("<RequestId>req-1</RequestId>", body)

    async def test_omits_resource_when_absent(self):
        request = MagicMock()
        exc = S3Error(
            code="AccessDenied",
            message="Access Denied",
            status_code=403,
        )

        with patch(
            "app.handlers.get_context_var",
            return_value="req-2",
        ):
            response = await s3_error_handler(request, exc)

        body = response.body.decode()
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("<Resource>", body)
        self.assertIn("<Code>AccessDenied</Code>", body)
