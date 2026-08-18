# tests/s3/test_validation.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import OBJECT_KEY_MAX_BYTES
from app.errors import S3InvalidBucketNameError, S3ObjectKeyInvalidError
from app.s3.validation import validate_bucket_name, validate_objekt_key


class TestValidateBucketName(unittest.TestCase):
    def _assert_rejects(self, bucket_name):
        resource = f"/{bucket_name}"

        with self.assertRaises(S3InvalidBucketNameError) as ctx:
            validate_bucket_name(bucket_name, resource)

        self.assertEqual(ctx.exception.resource, resource)

    def test_accepts_shortest_name(self):
        self.assertIsNone(validate_bucket_name("abc", "/abc"))

    def test_accepts_hyphenated_name(self):
        self.assertIsNone(validate_bucket_name("my-bucket", "/my-bucket"))

    def test_accepts_name_with_period(self):
        self.assertIsNone(validate_bucket_name("my.bucket", "/my.bucket"))

    def test_accepts_name_with_digits(self):
        self.assertIsNone(validate_bucket_name("bucket123", "/bucket123"))

    def test_accepts_mixed_hyphen_period_digits(self):
        self.assertIsNone(validate_bucket_name("a1-b2.c3", "/a1-b2.c3"))

    def test_accepts_dashes_and_periods(self):
        self.assertIsNone(
            validate_bucket_name("my-bucket.1", "/my-bucket.1"),
        )

    def test_accepts_longest_name(self):
        name = "a" * 63
        self.assertIsNone(validate_bucket_name(name, f"/{name}"))

    def test_rejects_empty_name(self):
        self._assert_rejects("")

    def test_rejects_too_short(self):
        self._assert_rejects("ab")

    def test_rejects_too_long(self):
        self._assert_rejects("a" * 64)

    def test_rejects_uppercase(self):
        self._assert_rejects("MyBucket")

    def test_rejects_underscore(self):
        self._assert_rejects("Bad_Name")
        self._assert_rejects("_bucket")

    def test_rejects_leading_dash(self):
        self._assert_rejects("-bucket")

    def test_rejects_trailing_dash(self):
        self._assert_rejects("bucket-")

    def test_rejects_leading_period(self):
        self._assert_rejects(".bucket")

    def test_rejects_trailing_period(self):
        self._assert_rejects("bucket.")

    def test_rejects_adjacent_periods(self):
        self._assert_rejects("my..bucket")
        self._assert_rejects("bucket..name")

    def test_rejects_period_next_to_dash(self):
        self._assert_rejects("my.-bucket")
        self._assert_rejects("my-.bucket")

    def test_rejects_ip_address(self):
        self._assert_rejects("192.168.1.1")

    def test_rejects_reserved_prefixes(self):
        self._assert_rejects("xn--example")
        self._assert_rejects("sthree-example")
        self._assert_rejects("amzn-s3-demo-example")

    def test_rejects_reserved_suffixes(self):
        self._assert_rejects("example-s3alias")
        self._assert_rejects("example--ol-s3")
        self._assert_rejects("example.mrap")
        self._assert_rejects("example--x-s3")
        self._assert_rejects("example--table-s3")


class TestValidateObjektKey(unittest.TestCase):
    def _assert_rejects(self, object_key):
        resource = f"/photos/{object_key}"

        with self.assertRaises(S3ObjectKeyInvalidError) as ctx:
            validate_objekt_key(object_key, resource)

        self.assertEqual(ctx.exception.resource, resource)

    def _assert_accepts(self, object_key):
        self.assertIsNone(
            validate_objekt_key(object_key, f"/photos/{object_key}"),
        )

    def test_accepts_flat_key(self):
        self._assert_accepts("file.txt")
        self._assert_accepts("cat.png")

    def test_accepts_nested_key(self):
        self._assert_accepts("dir/file.txt")
        self._assert_accepts("dir/subdir/file.txt")
        self._assert_accepts("photos/2024/cat.png")

    def test_accepts_unicode_key(self):
        self._assert_accepts("фото/кот.jpg")
        self._assert_accepts("資料/report.pdf")

    def test_accepts_backslash(self):
        self._assert_accepts("foo\\bar")

    def test_accepts_key_at_max_utf8_bytes(self):
        key = "a" * OBJECT_KEY_MAX_BYTES
        self._assert_accepts(key)

    def test_accepts_multibyte_key_at_max_utf8_bytes(self):
        key = "я" * (OBJECT_KEY_MAX_BYTES // 2)
        self.assertEqual(len(key.encode("utf-8")), OBJECT_KEY_MAX_BYTES)
        self._assert_accepts(key)

    def test_rejects_empty_key(self):
        self._assert_rejects("")

    def test_rejects_dot_key(self):
        self._assert_rejects(".")

    def test_rejects_parent_key(self):
        self._assert_rejects("..")

    def test_rejects_key_longer_than_max_bytes(self):
        self._assert_rejects("a" * (OBJECT_KEY_MAX_BYTES + 1))

    def test_rejects_multibyte_key_longer_than_max_bytes(self):
        self._assert_rejects("я" * OBJECT_KEY_MAX_BYTES)

    def test_rejects_multibyte_key_one_byte_over_limit(self):
        key = ("я" * (OBJECT_KEY_MAX_BYTES // 2)) + "a"
        self.assertEqual(len(key.encode("utf-8")), OBJECT_KEY_MAX_BYTES + 1)
        self.assertLess(len(key), OBJECT_KEY_MAX_BYTES)
        self._assert_rejects(key)

    def test_rejects_null_byte(self):
        self._assert_rejects("cat\x00.png")

    def test_rejects_surrogate_code_point(self):
        self._assert_rejects("cat\ud800.png")

    def test_rejects_leading_slash(self):
        self._assert_rejects("/cat.png")
        self._assert_rejects("/foo")

    def test_rejects_trailing_slash(self):
        self._assert_rejects("photos/")
        self._assert_rejects("foo/")

    def test_rejects_repeated_slashes(self):
        self._assert_rejects("photos//cat.png")
        self._assert_rejects("foo//bar")

    def test_rejects_dot_segment(self):
        self._assert_rejects("photos/./cat.png")
        self._assert_rejects("foo/./bar")

    def test_rejects_parent_segment(self):
        self._assert_rejects("photos/../../etc/passwd")
        self._assert_rejects("foo/../bar")
        self._assert_rejects("../foo")
        self._assert_rejects("foo/..")
