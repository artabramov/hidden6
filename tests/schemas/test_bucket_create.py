# tests/schemas/test_bucket_create.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.bucket_create import BucketCreateRequest


class TestBucketCreateRequest(unittest.TestCase):
    def test_accepts_valid_bucket_name(self):
        data = BucketCreateRequest(bucket_name="my-bucket")
        self.assertEqual(data.bucket_name, "my-bucket")

    def test_rejects_invalid_bucket_name(self):
        with self.assertRaises(ValidationError):
            BucketCreateRequest(bucket_name="Bad_Name")

    def test_rejects_extra_fields(self):
        with self.assertRaises(ValidationError):
            BucketCreateRequest(bucket_name="my-bucket", extra="nope")

    def test_requires_bucket_name(self):
        with self.assertRaises(ValidationError):
            BucketCreateRequest()
