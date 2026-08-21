# app/s3/bucket.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from app.constants import SECONDS_PER_DAY, SECONDS_PER_YEAR
from app.errors import (
    S3AccessDeniedError,
    S3BucketNotFoundError,
)
from app.models.bucket import S3Bucket
from app.models.user import User
from app.repositories.orm import ORMRepository


async def load_bucket(
    repo: ORMRepository,
    bucket_name: str,
    user: User,
    resource: str,
) -> S3Bucket:
    """
    Load a bucket for an object operation and verify that the user
    is allowed to access it.
    """
    bucket = await repo.select(S3Bucket, bucket_name=bucket_name)

    if bucket is None:
        raise S3BucketNotFoundError(resource)
    if not user.is_root and bucket.user_id != user.id:
        raise S3AccessDeniedError(resource)

    return bucket


def bucket_default_object_lock(
    bucket: S3Bucket,
    now: int | None = None,
) -> tuple[str | None, int | None]:
    """
    Resolve the default object lock mode and retention deadline
    for a new object version.
    """
    if not bucket.object_lock_enabled or bucket.default_lock_mode is None:
        return None, None

    now = int(time.time()) if now is None else now

    if bucket.default_retention_days is not None:
        retain_until = now + bucket.default_retention_days * SECONDS_PER_DAY
    elif bucket.default_retention_years is not None:
        retain_until = now + bucket.default_retention_years * SECONDS_PER_YEAR
    else:
        return None, None

    return bucket.default_lock_mode, retain_until
