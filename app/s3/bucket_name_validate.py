# app/s3/bucket_name_validate.py
# SPDX-License-Identifier: GPL-3.0-only

import re

from app.errors import S3InvalidBucketNameError

# AWS S3 bucket naming (DNS-compliant). The pattern also carries the
# length limits, because a name is one leading character, up to 61 in
# the middle, and one trailing character.
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_IP_ADDRESS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def bucket_name_validate(bucket_name: str, resource: str) -> None:
    """
    Reject a bucket name that violates S3 DNS naming rules before it
    reaches storage, where the name becomes a directory.

    Raises:
        S3InvalidBucketNameError: Name is not a valid bucket name.
    """
    if not _BUCKET_NAME_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)

    if ".." in bucket_name or ".-" in bucket_name or "-." in bucket_name:
        raise S3InvalidBucketNameError(resource)

    if _IP_ADDRESS_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)
