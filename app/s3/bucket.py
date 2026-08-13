# app/s3/bucket.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import re

from app.errors import (
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3InvalidBucketNameError,
)
from app.models.bucket import Bucket
from app.models.user import User
from app.repositories.orm import ORMRepository

# AWS S3 bucket naming (DNS-compliant). The pattern also carries the
# length limits, because a name is one leading character, up to 61 in
# the middle, and one trailing character.
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_IP_ADDRESS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def bucket_dir(buckets_dir: str, bucket_name: str, resource: str) -> str:
    """
    Resolve a bucket name to the directory holding its objects. A name
    that violates S3 DNS naming rules is rejected before it reaches
    storage, where the name becomes a directory of its own.

    Raises:
        S3InvalidBucketNameError: Name is not a valid bucket name.
    """
    if not _BUCKET_NAME_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)

    if ".." in bucket_name or ".-" in bucket_name or "-." in bucket_name:
        raise S3InvalidBucketNameError(resource)

    if _IP_ADDRESS_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)

    return os.path.join(buckets_dir, bucket_name)


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
