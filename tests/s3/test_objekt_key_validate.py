# tests/s3/test_objekt_key_validate.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.errors import S3ObjektKeyInvalidError
from app.s3.objekt_key_validate import objekt_key_validate


class TestObjektKeyValidate(unittest.TestCase):
    def _assert_rejects(self, object_key):
        resource = f"/photos/{object_key}"

        with self.assertRaises(S3ObjektKeyInvalidError) as ctx:
            objekt_key_validate(object_key, resource)

        self.assertEqual(ctx.exception.resource, resource)

    def test_accepts_flat_key(self):
        self.assertIsNone(objekt_key_validate("cat.png", "/photos/cat.png"))

    def test_accepts_nested_key(self):
        key = "photos/2024/cat.png"
        self.assertIsNone(objekt_key_validate(key, f"/photos/{key}"))

    def test_accepts_key_at_max_length(self):
        key = "a" * OBJEKT_KEY_MAX_BYTES
        self.assertIsNone(objekt_key_validate(key, f"/photos/{key}"))

    def test_rejects_empty_key(self):
        self._assert_rejects("")

    def test_rejects_key_longer_than_max_bytes(self):
        self._assert_rejects("a" * (OBJEKT_KEY_MAX_BYTES + 1))

    def test_rejects_multibyte_key_longer_than_max_bytes(self):
        self._assert_rejects("я" * OBJEKT_KEY_MAX_BYTES)

    def test_rejects_null_byte(self):
        self._assert_rejects("cat\x00.png")

    def test_rejects_leading_slash(self):
        self._assert_rejects("/cat.png")

    def test_rejects_trailing_slash(self):
        self._assert_rejects("photos/")

    def test_rejects_repeated_slashes(self):
        self._assert_rejects("photos//cat.png")

    def test_rejects_dot_segment(self):
        self._assert_rejects("photos/./cat.png")

    def test_rejects_parent_segment(self):
        self._assert_rejects("photos/../../etc/passwd")
