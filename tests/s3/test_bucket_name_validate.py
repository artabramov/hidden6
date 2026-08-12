# tests/s3/test_bucket_name_validate.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.errors import S3InvalidBucketNameError
from app.s3.bucket_name_validate import bucket_name_validate


class TestBucketNameValidate(unittest.TestCase):
    def test_accepts_valid_bucket_name(self):
        self.assertIsNone(bucket_name_validate("my-bucket", "/my-bucket"))

    def test_rejects_invalid_bucket_name(self):
        with self.assertRaises(S3InvalidBucketNameError) as ctx:
            bucket_name_validate("Bad_Name", "/Bad_Name")

        self.assertEqual(ctx.exception.resource, "/Bad_Name")

    def test_rejects_empty_bucket_name(self):
        with self.assertRaises(S3InvalidBucketNameError):
            bucket_name_validate("", "/")
