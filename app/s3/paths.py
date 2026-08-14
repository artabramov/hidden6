# app/s3/paths.py
# SPDX-License-Identifier: GPL-3.0-only

import os


def bucket_path(
    buckets_dir: str,
    bucket_name: str,
) -> str:
    """
    Filesystem path of a bucket directory under the buckets root.
    """
    return os.path.join(buckets_dir, bucket_name)


def objekt_path(
    buckets_dir: str,
    bucket_name: str,
    object_key: str,
) -> tuple[str, str]:
    """
    Filesystem paths of a bucket directory and an object stored under
    its validated S3 key.

    Raises:
        ValueError: Resolved object path is outside its bucket directory.
    """
    resolved_bucket = bucket_path(buckets_dir, bucket_name)
    resolved_object = os.path.join(resolved_bucket, object_key)

    if resolved_object == resolved_bucket:
        raise ValueError("Object path resolves to bucket directory")

    if os.path.commonpath(
        [resolved_bucket, resolved_object],
    ) != resolved_bucket:
        raise ValueError("Object path escapes bucket directory")

    return resolved_bucket, resolved_object


def multipart_path(
    tmp_dir: str,
    upload_id: str,
) -> str:
    """
    Filesystem path of the staging directory for a multipart upload.
    """
    return os.path.join(tmp_dir, upload_id)


def multipart_part_path(
    upload_dir: str,
    part_number: int,
) -> str:
    """
    Filesystem path of a staged multipart upload part.
    """
    return os.path.join(upload_dir, f"{part_number}.part")


def version_path(
    versions_dir: str,
    bucket_id: int,
    version_id: str,
) -> str:
    """
    Filesystem path of a retained non-current object version.
    """
    return os.path.join(versions_dir, str(bucket_id), version_id)
