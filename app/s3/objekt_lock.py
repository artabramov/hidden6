# app/s3/objekt_lock.py
# SPDX-License-Identifier: GPL-3.0-only

from app.constants import BUCKET_VERSIONING_ENABLED
from app.errors import S3BucketStateInvalidError
from app.models.bucket import Bucket


def set_bucket_objekt_lock_configuration(
    bucket: Bucket,
    objekt_lock_enabled: str | None,
    default_lock_mode: str | None,
    default_retention_days: int | None,
    default_retention_years: int | None,
    resource: str,
) -> None:
    """
    Apply an S3 Object Lock configuration to a bucket.

    Object Lock requires bucket versioning to be Enabled. Once enabled,
    Object Lock remains enabled. An absent default retention rule removes
    only the bucket default and does not disable Object Lock.
    """
    if bucket.versioning_status != BUCKET_VERSIONING_ENABLED:
        raise S3BucketStateInvalidError(resource)

    if objekt_lock_enabled == "Enabled":
        bucket.object_lock_enabled = True

    bucket.default_lock_mode = default_lock_mode
    bucket.default_retention_days = default_retention_days
    bucket.default_retention_years = default_retention_years
