# tests/xml/test_render_error.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.errors import S3Error
from app.xml.render_error import render_error


class TestRenderError(unittest.TestCase):
    def test_render_with_resource(self):
        exc = S3Error(
            code="InvalidBucketName",
            message="The specified bucket is not valid.",
            status_code=400,
            resource="/Bad_Name",
        )
        xml = render_error(exc, "req-1")

        self.assertIn("<Error>", xml)
        self.assertIn("<Code>InvalidBucketName</Code>", xml)
        self.assertIn(
            "<Message>The specified bucket is not valid.</Message>",
            xml,
        )
        self.assertIn("<Resource>/Bad_Name</Resource>", xml)
        self.assertIn("<RequestId>req-1</RequestId>", xml)

    def test_omits_resource_when_absent(self):
        exc = S3Error(
            code="AccessDenied",
            message="Access Denied",
            status_code=403,
        )
        xml = render_error(exc, "req-2")

        self.assertNotIn("<Resource>", xml)
        self.assertIn("<Code>AccessDenied</Code>", xml)

    def test_escapes_xml_special_characters(self):
        exc = S3Error(
            code="InvalidArgument",
            message="a & b",
            status_code=400,
            resource="/x<y",
        )
        xml = render_error(exc, "req-3")

        self.assertIn("<Message>a &amp; b</Message>", xml)
        self.assertIn("<Resource>/x&lt;y</Resource>", xml)
