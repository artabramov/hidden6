# app/s3/versioning.py
# SPDX-License-Identifier: GPL-3.0-only

from app.constants import (
    BUCKET_VERSIONING_DISABLED,
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
)
from app.models.bucket import Bucket


def get_bucket_versioning_status(bucket: Bucket) -> str | None:
    """
    Return the S3 VersioningConfiguration Status value for a bucket.

    Disabled is an internal state representing a bucket where versioning
    has never been enabled and is therefore exposed without a Status
    value. Enabled and Suspended are returned as their S3 values.
    """
    if bucket.versioning_status == BUCKET_VERSIONING_DISABLED:
        return None

    return bucket.versioning_status


def set_bucket_versioning_status(
    bucket: Bucket,
    status: str,
) -> None:
    """
    Apply an S3 bucket versioning state transition.

    A bucket may move from Disabled to Enabled, from Enabled to
    Suspended, and from Suspended back to Enabled. Once versioning has
    been enabled, the bucket never returns to Disabled.
    """
    if status not in (
        BUCKET_VERSIONING_ENABLED,
        BUCKET_VERSIONING_SUSPENDED,
    ):
        raise ValueError("Invalid bucket versioning status")

    if (
        bucket.versioning_status == BUCKET_VERSIONING_DISABLED
        and status == BUCKET_VERSIONING_SUSPENDED
    ):
        raise ValueError("Versioning cannot be suspended before it is enabled")

    bucket.versioning_status = status
