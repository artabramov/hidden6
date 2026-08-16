# app/s3/versioning.py
# SPDX-License-Identifier: GPL-3.0-only

from app.constants import (
    BUCKET_VERSIONING_DISABLED,
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
)
from app.errors import S3IllegalVersioningConfigurationError
from app.models.bucket import Bucket


def get_bucket_versioning_status(bucket: Bucket) -> str | None:
    """
    Return the S3 versioning status for a bucket.

    Disabled is an internal state representing a bucket where versioning
    has never been configured and is exposed through the S3 API without
    a Status value.
    """
    if bucket.versioning_status == BUCKET_VERSIONING_DISABLED:
        return None

    return bucket.versioning_status


def set_bucket_versioning_status(
    bucket: Bucket,
    versioning_status: str,
    resource: str,
) -> None:
    """
    Apply an S3 versioning state to a bucket.

    The S3 API accepts Enabled and Suspended. Disabled is an internal
    state representing a bucket where versioning has never been
    configured and cannot be restored through the S3 API.
    """
    if versioning_status not in (
        BUCKET_VERSIONING_ENABLED,
        BUCKET_VERSIONING_SUSPENDED,
    ):
        raise S3IllegalVersioningConfigurationError(resource)

    bucket.versioning_status = versioning_status
