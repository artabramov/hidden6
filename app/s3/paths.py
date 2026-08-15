# app/s3/paths.py
# SPDX-License-Identifier: GPL-3.0-only

import os


def resolve_bucket_path(
    buckets_dir: str,
    bucket_name: str,
) -> str:
    """
    Filesystem path of a bucket directory under the buckets root.
    """
    return os.path.join(buckets_dir, bucket_name)


def resolve_objekt_path(
    buckets_dir: str,
    bucket_name: str,
    objekt_key: str,
) -> tuple[str, str]:
    """
    Filesystem paths of a bucket directory and an object stored under
    its validated S3 key.

    Raises:
        ValueError: Resolved object path is outside its bucket directory.
    """
    resolved_bucket = resolve_bucket_path(buckets_dir, bucket_name)
    resolved_objekt = os.path.join(resolved_bucket, objekt_key)

    if resolved_objekt == resolved_bucket:
        raise ValueError("Object path resolves to bucket directory")

    if os.path.commonpath(
        [resolved_bucket, resolved_objekt],
    ) != resolved_bucket:
        raise ValueError("Object path escapes bucket directory")

    return resolved_bucket, resolved_objekt


def resolve_multipart_path(
    tmp_dir: str,
    upload_id: str,
) -> str:
    """
    Filesystem path of the staging directory for a multipart upload.
    """
    return os.path.join(tmp_dir, upload_id)


def resolve_multipart_part_path(
    upload_dir: str,
    part_number: int,
) -> str:
    """
    Filesystem path of a staged multipart upload part.
    """
    return os.path.join(upload_dir, f"{part_number}.part")


def resolve_version_path(
    versions_dir: str,
    bucket_id: int,
    version_id: str,
) -> str:
    """
    Filesystem path of a retained non-current object version.
    """
    return os.path.join(versions_dir, str(bucket_id), version_id)


def resolve_staged_path(
    tmp_dir: str,
    filename: str,
) -> str:
    """
    Filesystem path of a temporary staged object file under tmp.
    """
    return os.path.join(tmp_dir, filename)
