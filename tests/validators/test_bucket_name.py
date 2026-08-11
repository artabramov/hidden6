# tests/validators/test_bucket_name.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.validators.bucket_name import validate_bucket_name


class TestValidateBucketName(unittest.TestCase):
    def test_accepts_valid_names(self):
        self.assertEqual(validate_bucket_name("abc"), "abc")
        self.assertEqual(validate_bucket_name("my-bucket.1"), "my-bucket.1")

    def test_rejects_too_short(self):
        with self.assertRaises(ValueError):
            validate_bucket_name("ab")

    def test_rejects_uppercase(self):
        with self.assertRaises(ValueError):
            validate_bucket_name("MyBucket")

    def test_rejects_adjacent_periods(self):
        with self.assertRaises(ValueError):
            validate_bucket_name("my..bucket")

    def test_rejects_ip_address(self):
        with self.assertRaises(ValueError):
            validate_bucket_name("192.168.1.1")
