# app/s3/bucket_load.py
# SPDX-License-Identifier: GPL-3.0-only

from app.errors import S3AccessDeniedError, S3BucketNotFoundError
from app.models.bucket import Bucket
from app.models.user import User
from app.repositories.orm import ORMRepository


async def bucket_load(
    repo: ORMRepository,
    bucket_name: str,
    user: User,
    resource: str,
) -> Bucket:
    """
    Load the bucket addressed by an object operation and authorize the
    caller against it (ADR-21): the owner and root are allowed.
    """
    bucket = await repo.select(Bucket, bucket_name=bucket_name)

    if bucket is None:
        raise S3BucketNotFoundError(resource)
    if not user.is_root and bucket.user_id != user.id:
        raise S3AccessDeniedError(resource)

    return bucket
