# tests/xml/test_parse_multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import S3_XMLNS
from app.xml.parse_multipart_complete import parse_multipart_complete


class TestParseMultipartComplete(unittest.TestCase):
    def test_parses_parts(self):
        body = (
            b"<CompleteMultipartUpload>"
            b"<Part><PartNumber>1</PartNumber>"
            b'<ETag>"aaa"</ETag></Part>'
            b"<Part><PartNumber>2</PartNumber>"
            b'<ETag>"bbb"</ETag></Part>'
            b"</CompleteMultipartUpload>"
        )

        parts = parse_multipart_complete(body)

        self.assertEqual([p.part_number for p in parts], [1, 2])
        self.assertEqual([p.etag for p in parts], ["aaa", "bbb"])

    def test_parses_namespaced_parts(self):
        body = (
            f'<CompleteMultipartUpload xmlns="{S3_XMLNS}">'
            "<Part><PartNumber>1</PartNumber>"
            "<ETag>AAA</ETag></Part>"
            "</CompleteMultipartUpload>"
        ).encode()

        parts = parse_multipart_complete(body)

        self.assertEqual(parts[0].part_number, 1)
        self.assertEqual(parts[0].etag, "aaa")

    def test_parses_indented_body(self):
        body = (
            b"<CompleteMultipartUpload>\n"
            b"  <Part>\n"
            b"    <PartNumber>1</PartNumber>\n"
            b'    <ETag>"aaa"</ETag>\n'
            b"  </Part>\n"
            b"</CompleteMultipartUpload>\n"
        )

        parts = parse_multipart_complete(body)

        self.assertEqual(parts[0].part_number, 1)
        self.assertEqual(parts[0].etag, "aaa")

    def test_ignores_unknown_part_children(self):
        body = (
            b"<CompleteMultipartUpload><Part>"
            b"<PartNumber>1</PartNumber>"
            b'<ETag>"aaa"</ETag>'
            b"<ChecksumCRC32>deadbeef</ChecksumCRC32>"
            b"</Part></CompleteMultipartUpload>"
        )

        parts = parse_multipart_complete(body)

        self.assertEqual(parts[0].part_number, 1)
        self.assertEqual(parts[0].etag, "aaa")

    def test_rejects_malformed_xml(self):
        with self.assertRaises(ValueError):
            parse_multipart_complete(b"<CompleteMultipartUpload>")

    def test_rejects_unexpected_root(self):
        with self.assertRaises(ValueError):
            parse_multipart_complete(b"<Nope><Part/></Nope>")

    def test_rejects_empty_part_list(self):
        with self.assertRaises(ValueError):
            parse_multipart_complete(
                b"<CompleteMultipartUpload></CompleteMultipartUpload>",
            )

    def test_rejects_part_without_etag(self):
        with self.assertRaises(ValueError):
            parse_multipart_complete(
                b"<CompleteMultipartUpload><Part>"
                b"<PartNumber>1</PartNumber>"
                b"</Part></CompleteMultipartUpload>",
            )

    def test_rejects_non_numeric_part_number(self):
        with self.assertRaises(ValueError):
            parse_multipart_complete(
                b"<CompleteMultipartUpload><Part>"
                b"<PartNumber>one</PartNumber><ETag>aaa</ETag>"
                b"</Part></CompleteMultipartUpload>",
            )

    def test_rejects_part_number_below_one(self):
        with self.assertRaises(ValueError):
            parse_multipart_complete(
                b"<CompleteMultipartUpload><Part>"
                b"<PartNumber>0</PartNumber><ETag>aaa</ETag>"
                b"</Part></CompleteMultipartUpload>",
            )
