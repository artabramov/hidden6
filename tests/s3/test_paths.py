# tests/s3/test_paths.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.s3.paths import (
    multipart_part_path,
    multipart_path,
    version_path,
)


class TestMultipartPath(unittest.TestCase):
    def test_resolves_upload_dir(self):
        self.assertEqual(
            multipart_path("/mnt/tmp", "beef"),
            "/mnt/tmp/beef",
        )

    def test_resolves_part_file(self):
        self.assertEqual(
            multipart_part_path("/mnt/tmp/beef", 3),
            "/mnt/tmp/beef/3.part",
        )


class TestVersionPath(unittest.TestCase):
    def test_resolves_with_int_bucket_id(self):
        self.assertEqual(
            version_path("/mnt/versions", 7, "v1a2b3"),
            "/mnt/versions/7/v1a2b3",
        )

    def test_resolves_with_str_bucket_id(self):
        self.assertEqual(
            version_path("/mnt/versions", "7", "v1a2b3"),
            "/mnt/versions/7/v1a2b3",
        )
