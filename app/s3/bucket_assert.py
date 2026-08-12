# app/s3/bucket_assert.py
# SPDX-License-Identifier: GPL-3.0-only

from app.errors import S3BucketNotFoundError
from app.repositories.file import isdir


async def bucket_assert(bucket_path: str, resource: str) -> None:
    """
    Ensure the bucket directory backing the bucket row still exists.
    """
    if not await isdir(bucket_path):
        raise S3BucketNotFoundError(resource)
