# app/s3/paths.py
# SPDX-License-Identifier: GPL-3.0-only

import os

from app.errors import S3ObjektKeyInvalidError


def bucket_path(
    buckets_dir: str,
    bucket_name: str,
) -> str:
    """
    Resolve a bucket name to the directory holding its objects.
    """
    return os.path.join(buckets_dir, bucket_name)


def objekt_path(
    buckets_dir: str,
    bucket_name: str,
    object_key: str,
) -> tuple[str, str]:
    """
    Resolve an object key to its bucket directory and filesystem path.

    Raises:
        S3ObjektKeyInvalidError: Key escapes the bucket directory.
    """
    resolved_bucket = bucket_path(buckets_dir, bucket_name)
    resolved_object = os.path.normpath(
        os.path.join(resolved_bucket, object_key),
    )

    if resolved_object == resolved_bucket:
        raise S3ObjektKeyInvalidError(f"/{bucket_name}/{object_key}")

    if os.path.commonpath(
        [resolved_bucket, resolved_object],
    ) != resolved_bucket:
        raise S3ObjektKeyInvalidError(f"/{bucket_name}/{object_key}")

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
