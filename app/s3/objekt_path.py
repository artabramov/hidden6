# app/s3/objekt_path.py
# SPDX-License-Identifier: GPL-3.0-only

import os

from app.errors import S3ObjektKeyInvalidError

# NOTE (ADR-24): S3 object keys map to nested filesystem paths.
# A key is stored as a path relative to the bucket directory, so the
# key photos/2024/cat.png becomes a file in nested directories that
# are created on upload. Because directories and files share one
# namespace on disk, a key colliding with a stored object is rejected
# instead of being flattened into a single filename.


def objekt_path(
    bucket_path: str,
    object_key: str,
    resource: str,
) -> str:
    """
    Map an object key onto a path inside the bucket directory. Keys are
    validated before this point; the containment check keeps a key that
    still resolves outside the bucket from reaching the filesystem.
    """
    object_path = os.path.normpath(os.path.join(bucket_path, object_key))

    if object_path == bucket_path:
        raise S3ObjektKeyInvalidError(resource)
    if os.path.commonpath([bucket_path, object_path]) != bucket_path:
        raise S3ObjektKeyInvalidError(resource)

    return object_path
