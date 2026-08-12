# tests/s3/test_multipart_etag.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import unittest

from app.s3.multipart_etag import multipart_etag


class TestMultipartEtag(unittest.TestCase):
    def test_hashes_part_digests(self):
        hashes = [
            hashlib.md5(b"first").hexdigest(),
            hashlib.md5(b"second").hexdigest(),
        ]
        digests = b"".join(bytes.fromhex(value) for value in hashes)
        expected = hashlib.md5(digests).hexdigest()

        self.assertEqual(
            multipart_etag(hashes),
            f"{expected}-2",
        )

    def test_single_part_is_suffixed_too(self):
        etag = multipart_etag([hashlib.md5(b"first").hexdigest()])

        self.assertTrue(etag.endswith("-1"))
