# tests/s3/test_etag.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import unittest

from app.s3.etag import etag_construct, etag_normalize


class TestEtagNormalize(unittest.TestCase):
    def test_strips_quotes(self):
        self.assertEqual(etag_normalize('"abc123"'), "abc123")

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(etag_normalize('  "abc123"  '), "abc123")

    def test_lowercases_hash(self):
        self.assertEqual(etag_normalize('"ABC123"'), "abc123")

    def test_keeps_bare_hash(self):
        self.assertEqual(etag_normalize("abc123"), "abc123")

    def test_keeps_multipart_suffix(self):
        self.assertEqual(etag_normalize('"abc123-2"'), "abc123-2")


class TestEtagConstruct(unittest.TestCase):
    def test_hashes_part_digests(self):
        hashes = [
            hashlib.md5(b"first").hexdigest(),
            hashlib.md5(b"second").hexdigest(),
        ]
        digests = b"".join(bytes.fromhex(value) for value in hashes)
        expected = hashlib.md5(digests).hexdigest()

        self.assertEqual(
            etag_construct(hashes),
            f"{expected}-2",
        )

    def test_single_part_is_suffixed_too(self):
        etag = etag_construct([hashlib.md5(b"first").hexdigest()])

        self.assertTrue(etag.endswith("-1"))
