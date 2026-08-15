# tests/s3/test_paths.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import unittest

from app.s3.paths import (
    resolve_bucket_path,
    resolve_multipart_part_path,
    resolve_multipart_path,
    resolve_objekt_path,
    resolve_staged_path,
    resolve_version_path,
)


class TestBucketPath(unittest.TestCase):
    def test_resolves_bucket_directory(self):
        self.assertEqual(
            resolve_bucket_path("/mnt/buckets", "photos"),
            "/mnt/buckets/photos",
        )


class TestObjektPath(unittest.TestCase):
    def test_resolves_nested_key(self):
        resolved_bucket, resolved_object = resolve_objekt_path(
            "/mnt/buckets",
            "photos",
            "2024/summer/cat.png",
        )

        self.assertEqual(resolved_bucket, "/mnt/buckets/photos")
        self.assertEqual(
            resolved_object,
            "/mnt/buckets/photos/2024/summer/cat.png",
        )
        self.assertEqual(
            resolved_object,
            os.path.join(resolved_bucket, "2024/summer/cat.png"),
        )

    def test_rejects_absolute_key_with_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            resolve_objekt_path("/mnt/buckets", "photos", "/etc/passwd")

        self.assertIn("escapes bucket directory", str(ctx.exception))


class TestMultipartPath(unittest.TestCase):
    def test_resolves_upload_dir(self):
        self.assertEqual(
            resolve_multipart_path("/mnt/tmp", "beef"),
            "/mnt/tmp/beef",
        )

    def test_resolves_part_file(self):
        self.assertEqual(
            resolve_multipart_part_path("/mnt/tmp/beef", 3),
            "/mnt/tmp/beef/3.part",
        )


class TestResolveStagedPath(unittest.TestCase):
    def test_resolves_staged_file(self):
        self.assertEqual(
            resolve_staged_path("/mnt/tmp", "beef"),
            "/mnt/tmp/beef",
        )


class TestResolveVersionPath(unittest.TestCase):
    def test_resolves_with_int_bucket_id(self):
        self.assertEqual(
            resolve_version_path("/mnt/versions", 7, "v1a2b3"),
            "/mnt/versions/7/v1a2b3",
        )
