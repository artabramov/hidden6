# tests/s3/test_objekt_key_validate.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.errors import S3ObjektKeyInvalidError
from app.s3.objekt_key_validate import objekt_key_validate


class TestObjektKeyValidate(unittest.TestCase):
    def test_accepts_valid_object_key(self):
        self.assertIsNone(
            objekt_key_validate("photos/cat.png", "/photos/cat.png"),
        )

    def test_rejects_key_escaping_the_bucket(self):
        with self.assertRaises(S3ObjektKeyInvalidError) as ctx:
            objekt_key_validate("photos/../cat.png", "/b/photos/../cat.png")

        self.assertEqual(ctx.exception.resource, "/b/photos/../cat.png")

    def test_rejects_empty_object_key(self):
        with self.assertRaises(S3ObjektKeyInvalidError):
            objekt_key_validate("", "/b/")
