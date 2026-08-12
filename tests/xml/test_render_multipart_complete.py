# tests/xml/test_render_multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import S3_XMLNS
from app.xml.render_multipart_complete import render_multipart_complete


class TestRenderMultipartComplete(unittest.TestCase):
    def test_renders_complete_result(self):
        xml = render_multipart_complete(
            bucket_name="photos",
            object_key="2024/cat.png",
            etag="abc-2",
        )

        self.assertIn(f'xmlns="{S3_XMLNS}"', xml)
        self.assertIn(
            "<Location>/photos/2024/cat.png</Location>",
            xml,
        )
        self.assertIn("<Bucket>photos</Bucket>", xml)
        self.assertIn("<Key>2024/cat.png</Key>", xml)
        self.assertIn('<ETag>"abc-2"</ETag>', xml)

    def test_escapes_key(self):
        xml = render_multipart_complete(
            bucket_name="photos",
            object_key="a&b<c>.png",
            etag="abc-2",
        )

        self.assertIn("<Key>a&amp;b&lt;c&gt;.png</Key>", xml)
