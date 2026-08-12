# app/s3/objekt_dir.py
# SPDX-License-Identifier: GPL-3.0-only

import os

from app.errors import S3ObjektKeyInvalidError
from app.s3.bucket_dir import bucket_dir
from app.s3.objekt_key_validate import objekt_key_validate

# NOTE (ADR-24): S3 object keys map to nested filesystem paths.
# A key is stored as a path relative to the bucket directory, so the
# key photos/2024/cat.png becomes a file in nested directories that
# are created on upload. Because directories and files share one
# namespace on disk, a key colliding with a stored object is rejected
# instead of being flattened into a single filename.


def objekt_dir(
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

    bucket_path = bucket_dir(buckets_dir, bucket_name, resource)
    object_path = os.path.normpath(os.path.join(bucket_path, object_key))

    if object_path == bucket_path:
        raise S3ObjektKeyInvalidError(resource)

    if os.path.commonpath([bucket_path, object_path]) != bucket_path:
        raise S3ObjektKeyInvalidError(resource)

    return bucket_path, object_path
