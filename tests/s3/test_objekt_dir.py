# tests/s3/test_objekt_dir.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.errors import S3InvalidBucketNameError, S3ObjektKeyInvalidError
from app.s3.objekt_dir import objekt_dir


class TestObjektDir(unittest.TestCase):
    def test_resolves_flat_key(self):
        bucket_path, object_path = objekt_dir(
            "/mnt/buckets",
            "photos",
            "cat.png",
            "/photos/cat.png",
        )

        self.assertEqual(bucket_path, "/mnt/buckets/photos")
        self.assertEqual(object_path, "/mnt/buckets/photos/cat.png")

    def test_resolves_nested_key(self):
        bucket_path, object_path = objekt_dir(
            "/mnt/buckets",
            "photos",
            "2024/summer/cat.png",
            "/photos/2024/summer/cat.png",
        )

        self.assertEqual(bucket_path, "/mnt/buckets/photos")
        self.assertEqual(
            object_path,
            "/mnt/buckets/photos/2024/summer/cat.png",
        )

    def test_resolves_key_at_max_length(self):
        key = "a" * OBJEKT_KEY_MAX_BYTES
        _, object_path = objekt_dir(
            "/mnt/buckets",
            "photos",
            key,
            f"/photos/{key}",
        )

        self.assertEqual(object_path, f"/mnt/buckets/photos/{key}")

    def test_rejects_invalid_bucket_name(self):
        with self.assertRaises(S3InvalidBucketNameError):
            objekt_dir(
                "/mnt/buckets",
                "Bad_Name",
                "cat.png",
                "/Bad_Name/cat.png",
            )

    def test_rejects_key_escaping_the_bucket(self):
        with self.assertRaises(S3ObjektKeyInvalidError):
            objekt_dir(
                "/mnt/buckets",
                "photos",
                "../videos/cat.png",
                "/photos/../videos/cat.png",
            )

    def test_rejects_key_resolving_to_the_bucket(self):
        with self.assertRaises(S3ObjektKeyInvalidError):
            objekt_dir(
                "/mnt/buckets",
                "photos",
                "2024/..",
                "/photos/2024/..",
            )
