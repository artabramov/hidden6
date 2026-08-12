# tests/s3/test_etag_normalize.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.s3.etag_normalize import etag_normalize


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
