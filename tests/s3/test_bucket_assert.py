# tests/s3/test_bucket_assert.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import S3BucketNotFoundError  # noqa: E402
from app.s3.bucket_assert import bucket_assert  # noqa: E402


class TestBucketAssert(unittest.IsolatedAsyncioTestCase):
    async def test_passes_for_existing_dir(self):
        with patch(
            "app.s3.bucket_assert.isdir",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await bucket_assert("/mnt/buckets/photos", "/photos")

    async def test_missing_dir_raises(self):
        with patch(
            "app.s3.bucket_assert.isdir",
            new_callable=AsyncMock,
            return_value=False,
        ):
            with self.assertRaises(S3BucketNotFoundError):
                await bucket_assert("/mnt/buckets/photos", "/photos")
