# app/s3/paths.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import re

from app.errors import S3InvalidBucketNameError, S3ObjektKeyInvalidError
from app.s3.objekt import objekt_key_validate

# AWS S3 bucket naming (DNS-compliant). The pattern also carries the
# length limits, because a name is one leading character, up to 61 in
# the middle, and one trailing character.
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_IP_ADDRESS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def bucket_path(
    buckets_dir: str,
    bucket_name: str,
    resource: str,
) -> str:
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


def objekt_path(
    buckets_dir: str,
    bucket_name: str,
    object_key: str,
    resource: str,
) -> tuple[str, str]:
    """
    Resolve a validated object key to its bucket directory and
    filesystem path. The bucket name is validated before it reaches
    storage, where it becomes a directory of its own.

    Raises:
        S3InvalidBucketNameError: Bucket name is not valid.
        S3ObjektKeyInvalidError: Key is not a valid object key.
    """
    objekt_key_validate(object_key, resource)

    resolved_bucket = bucket_path(buckets_dir, bucket_name, resource)
    resolved_object = os.path.normpath(
        os.path.join(resolved_bucket, object_key),
    )

    if resolved_object == resolved_bucket:
        raise S3ObjektKeyInvalidError(resource)

    if os.path.commonpath(
        [resolved_bucket, resolved_object],
    ) != resolved_bucket:
        raise S3ObjektKeyInvalidError(resource)

    return resolved_bucket, resolved_object


def multipart_path(
    tmp_dir: str,
    upload_id: str,
) -> str:
    """
    Directory holding staged parts for one multipart upload. The
    upload_id is the leaf name under the shared temporary mount.
    """
    return os.path.join(tmp_dir, upload_id)


def multipart_part_path(
    upload_dir: str,
    part_number: int,
) -> str:
    """
    Final staged file for one multipart part number inside its
    upload directory.
    """
    return os.path.join(upload_dir, f"{part_number}.part")


def version_path(
    versions_dir: str,
    bucket_id: int | str,
    version_id: str,
) -> str:
    """
    Filesystem path for a non-current object version payload. Current
    object bytes stay on the key path (ADR-27); retained versions live
    under versions_dir grouped by bucket id.
    """
    return os.path.join(versions_dir, str(bucket_id), version_id)
