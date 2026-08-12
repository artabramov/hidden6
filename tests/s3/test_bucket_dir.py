# tests/s3/test_bucket_dir.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.errors import S3InvalidBucketNameError
from app.s3.bucket_dir import bucket_dir


class TestBucketDir(unittest.TestCase):
    def _assert_rejects(self, bucket_name):
        resource = f"/{bucket_name}"

        with self.assertRaises(S3InvalidBucketNameError) as ctx:
            bucket_dir("/mnt/buckets", bucket_name, resource)

        self.assertEqual(ctx.exception.resource, resource)

    def test_resolves_shortest_name(self):
        self.assertEqual(
            bucket_dir("/mnt/buckets", "abc", "/abc"),
            "/mnt/buckets/abc",
        )

    def test_resolves_dashes_and_periods(self):
        self.assertEqual(
            bucket_dir("/mnt/buckets", "my-bucket.1", "/my-bucket.1"),
            "/mnt/buckets/my-bucket.1",
        )

    def test_resolves_longest_name(self):
        name = "a" * 63
        self.assertEqual(
            bucket_dir("/mnt/buckets", name, f"/{name}"),
            f"/mnt/buckets/{name}",
        )

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

    def test_rejects_leading_dash(self):
        self._assert_rejects("-bucket")

    def test_rejects_adjacent_periods(self):
        self._assert_rejects("my..bucket")

    def test_rejects_period_next_to_dash(self):
        self._assert_rejects("my.-bucket")
        self._assert_rejects("my-.bucket")

    def test_rejects_ip_address(self):
        self._assert_rejects("192.168.1.1")
