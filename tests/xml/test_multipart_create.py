# tests/xml/test_multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import S3_XMLNS
from app.xml.multipart_create import render_initiate_multipart_xml


class TestRenderInitiateMultipartXml(unittest.TestCase):
    def test_renders_initiate_result(self):
        xml = render_initiate_multipart_xml(
            bucket_name="photos",
            object_key="2024/cat.png",
            upload_id="beef",
        )

        self.assertIn(f'xmlns="{S3_XMLNS}"', xml)
        self.assertIn("<Bucket>photos</Bucket>", xml)
        self.assertIn("<Key>2024/cat.png</Key>", xml)
        self.assertIn("<UploadId>beef</UploadId>", xml)

    def test_escapes_key(self):
        xml = render_initiate_multipart_xml(
            bucket_name="photos",
            object_key="a&b<c>.png",
            upload_id="beef",
        )

        self.assertIn("<Key>a&amp;b&lt;c&gt;.png</Key>", xml)
