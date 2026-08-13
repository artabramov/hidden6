# app/s3/objekt.py
# SPDX-License-Identifier: GPL-3.0-only

import os

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.errors import (
    S3ObjektKeyConflictError,
    S3ObjektKeyInvalidError,
    S3ObjektNotFoundError,
)
from app.models.bucket import Bucket
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import isdir, mktree
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_dir

# Segments that cannot be mapped onto a filesystem path. Empty rejects
# an empty key, a leading or trailing slash, and repeated slashes.
_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})

# NOTE (ADR-24): S3 object keys map to nested filesystem paths.
# A key is stored as a path relative to the bucket directory, so the
# key photos/2024/cat.png becomes a file in nested directories that
# are created on upload. Because directories and files share one
# namespace on disk, a key colliding with a stored object is rejected
# instead of being flattened into a single filename.


def objekt_key_validate(object_key: str, resource: str) -> None:
    """
    Reject an object key that cannot be stored as a path relative to
    the bucket directory: oversized, holding a null byte, or carrying a
    segment that is empty, a dot, or a double dot.

    Raises:
        S3ObjektKeyInvalidError: Key is not a valid object key.
    """
    if len(object_key.encode("utf-8")) > OBJEKT_KEY_MAX_BYTES:
        raise S3ObjektKeyInvalidError(resource)

    if "\x00" in object_key:
        raise S3ObjektKeyInvalidError(resource)

    if any(part in _FORBIDDEN_SEGMENTS for part in object_key.split("/")):
        raise S3ObjektKeyInvalidError(resource)


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


async def objekt_load(
    repo: ORMRepository,
    bucket: Bucket,
    object_key: str,
    resource: str,
) -> Objekt:
    """
    Load the Objekt row for a key inside a bucket. A missing row is
    reported as NoSuchKey — the same code S3 uses when the object
    is absent from the store.
    """
    objekt = await repo.select(
        Objekt,
        bucket_id=bucket.id,
        object_key=object_key,
    )

    if objekt is None:
        raise S3ObjektNotFoundError(resource)

    return objekt


async def objekt_mkdir(object_path: str, resource: str) -> None:
    """
    Create the directories carrying the key prefix. A prefix occupied
    by a stored object cannot become a directory, and neither can a
    key already used by a directory hold an object.
    """
    if await isdir(object_path):
        raise S3ObjektKeyConflictError(resource)

    try:
        await mktree(os.path.dirname(object_path))
    except (FileExistsError, NotADirectoryError) as exc:
        raise S3ObjektKeyConflictError(resource) from exc


async def objekt_upsert(
    repo: ORMRepository,
    bucket: Bucket,
    user: User,
    object_key: str,
    size_bytes: int,
    etag: str,
    content_type: str,
) -> Objekt:
    """
    Insert the Objekt row for a new key or update the existing row when
    the key is overwritten. Changes are flushed, not committed.
    """
    objekt = await repo.select(
        Objekt,
        bucket_id=bucket.id,
        object_key=object_key,
    )

    if objekt is None:
        objekt = Objekt(
            bucket_id=bucket.id,
            user_id=user.id,
            object_key=object_key,
            size_bytes=size_bytes,
            etag=etag,
            content_type=content_type,
        )
        return await repo.insert(objekt)

    objekt.user_id = user.id
    objekt.size_bytes = size_bytes
    objekt.etag = etag
    objekt.content_type = content_type

    return await repo.update(objekt)
