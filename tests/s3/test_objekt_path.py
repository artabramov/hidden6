# tests/s3/test_objekt_path.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import S3ObjektKeyInvalidError  # noqa: E402
from app.s3.objekt_path import objekt_path  # noqa: E402


class TestObjektPath(unittest.TestCase):
    def test_maps_flat_key(self):
        path = objekt_path(
            "/mnt/buckets/photos",
            "cat.png",
            "/photos/cat.png",
        )

        self.assertEqual(path, "/mnt/buckets/photos/cat.png")

    def test_maps_nested_key(self):
        path = objekt_path(
            "/mnt/buckets/photos",
            "2024/summer/cat.png",
            "/photos/2024/summer/cat.png",
        )

        self.assertEqual(
            path,
            "/mnt/buckets/photos/2024/summer/cat.png",
        )

    def test_rejects_key_escaping_the_bucket(self):
        with self.assertRaises(S3ObjektKeyInvalidError):
            objekt_path(
                "/mnt/buckets/photos",
                "../videos/cat.png",
                "/photos/../videos/cat.png",
            )

    def test_rejects_key_resolving_to_the_bucket(self):
        with self.assertRaises(S3ObjektKeyInvalidError):
            objekt_path(
                "/mnt/buckets/photos",
                "2024/..",
                "/photos/2024/..",
            )
