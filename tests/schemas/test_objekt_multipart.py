# tests/schemas/test_objekt_multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import S3_XMLNS
from app.schemas.objekt_multipart import (
    parse_complete_multipart_xml,
    render_complete_multipart_xml,
    render_initiate_multipart_xml,
)


class TestParseCompleteMultipartXml(unittest.TestCase):
    def test_parses_parts(self):
        body = (
            b"<CompleteMultipartUpload>"
            b"<Part><PartNumber>1</PartNumber>"
            b'<ETag>"aaa"</ETag></Part>'
            b"<Part><PartNumber>2</PartNumber>"
            b'<ETag>"bbb"</ETag></Part>'
            b"</CompleteMultipartUpload>"
        )

        parts = parse_complete_multipart_xml(body)

        self.assertEqual([p.part_number for p in parts], [1, 2])
        self.assertEqual([p.etag for p in parts], ["aaa", "bbb"])

    def test_parses_namespaced_parts(self):
        body = (
            f'<CompleteMultipartUpload xmlns="{S3_XMLNS}">'
            "<Part><PartNumber>1</PartNumber>"
            "<ETag>AAA</ETag></Part>"
            "</CompleteMultipartUpload>"
        ).encode()

        parts = parse_complete_multipart_xml(body)

        self.assertEqual(parts[0].part_number, 1)
        self.assertEqual(parts[0].etag, "aaa")

    def test_rejects_malformed_xml(self):
        with self.assertRaises(ValueError):
            parse_complete_multipart_xml(b"<CompleteMultipartUpload>")

    def test_rejects_unexpected_root(self):
        with self.assertRaises(ValueError):
            parse_complete_multipart_xml(b"<Nope><Part/></Nope>")

    def test_rejects_empty_part_list(self):
        with self.assertRaises(ValueError):
            parse_complete_multipart_xml(
                b"<CompleteMultipartUpload></CompleteMultipartUpload>",
            )

    def test_rejects_part_without_etag(self):
        with self.assertRaises(ValueError):
            parse_complete_multipart_xml(
                b"<CompleteMultipartUpload><Part>"
                b"<PartNumber>1</PartNumber>"
                b"</Part></CompleteMultipartUpload>",
            )

    def test_rejects_non_numeric_part_number(self):
        with self.assertRaises(ValueError):
            parse_complete_multipart_xml(
                b"<CompleteMultipartUpload><Part>"
                b"<PartNumber>one</PartNumber><ETag>aaa</ETag>"
                b"</Part></CompleteMultipartUpload>",
            )

    def test_rejects_part_number_below_one(self):
        with self.assertRaises(ValueError):
            parse_complete_multipart_xml(
                b"<CompleteMultipartUpload><Part>"
                b"<PartNumber>0</PartNumber><ETag>aaa</ETag>"
                b"</Part></CompleteMultipartUpload>",
            )


class TestRenderMultipartXml(unittest.TestCase):
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

    def test_renders_complete_result(self):
        xml = render_complete_multipart_xml(
            bucket_name="photos",
            object_key="2024/cat.png",
            etag="abc-2",
        )

        self.assertIn(
            "<Location>/photos/2024/cat.png</Location>",
            xml,
        )
        self.assertIn("<Bucket>photos</Bucket>", xml)
        self.assertIn("<Key>2024/cat.png</Key>", xml)
        self.assertIn('<ETag>"abc-2"</ETag>', xml)

    def test_escapes_key(self):
        xml = render_initiate_multipart_xml(
            bucket_name="photos",
            object_key="a&b<c>.png",
            upload_id="beef",
        )

        self.assertIn("<Key>a&amp;b&lt;c&gt;.png</Key>", xml)
