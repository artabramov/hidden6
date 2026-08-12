# tests/validators/test_object_key.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.validators.object_key import validate_object_key


class TestValidateObjectKey(unittest.TestCase):
    def test_accepts_flat_key(self):
        self.assertEqual(validate_object_key("cat.png"), "cat.png")

    def test_accepts_nested_key(self):
        key = "photos/2024/cat.png"
        self.assertEqual(validate_object_key(key), key)

    def test_accepts_key_at_max_length(self):
        key = "a" * OBJEKT_KEY_MAX_BYTES
        self.assertEqual(validate_object_key(key), key)

    def test_rejects_empty_key(self):
        with self.assertRaises(ValueError):
            validate_object_key("")

    def test_rejects_key_longer_than_max_bytes(self):
        with self.assertRaises(ValueError):
            validate_object_key("a" * (OBJEKT_KEY_MAX_BYTES + 1))

    def test_rejects_multibyte_key_longer_than_max_bytes(self):
        with self.assertRaises(ValueError):
            validate_object_key("я" * OBJEKT_KEY_MAX_BYTES)

    def test_rejects_null_byte(self):
        with self.assertRaises(ValueError):
            validate_object_key("cat\x00.png")

    def test_rejects_leading_slash(self):
        with self.assertRaises(ValueError):
            validate_object_key("/cat.png")

    def test_rejects_trailing_slash(self):
        with self.assertRaises(ValueError):
            validate_object_key("photos/")

    def test_rejects_repeated_slashes(self):
        with self.assertRaises(ValueError):
            validate_object_key("photos//cat.png")

    def test_rejects_dot_segment(self):
        with self.assertRaises(ValueError):
            validate_object_key("photos/./cat.png")

    def test_rejects_parent_segment(self):
        with self.assertRaises(ValueError):
            validate_object_key("photos/../../etc/passwd")
