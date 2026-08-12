# app/s3/bucket_name_validate.py
# SPDX-License-Identifier: GPL-3.0-only

from app.errors import S3InvalidBucketNameError
from app.validators.bucket_name import validate_bucket_name


def bucket_name_validate(bucket_name: str, resource: str) -> None:
    """
    Reject a bucket name that violates S3 DNS naming rules before it
    reaches storage, where the name becomes a directory.

    Raises:
        S3InvalidBucketNameError: Name is not a valid bucket name.
    """
    try:
        validate_bucket_name(bucket_name)
    except ValueError as exc:
        raise S3InvalidBucketNameError(resource) from exc
