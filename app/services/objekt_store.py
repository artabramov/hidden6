# app/services/objekt_store.py
# SPDX-License-Identifier: GPL-3.0-only

import os

from app.errors import (
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3ObjektKeyConflictError,
    S3ObjektKeyInvalidError,
)
from app.models.bucket import Bucket
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.file import isdir, mkdir
from app.repositories.orm import ORMRepository

# NOTE (ADR-24): S3 object keys map to nested filesystem paths.
# A key is stored as a path relative to the bucket directory, so the
# key photos/2024/cat.png becomes a file in nested directories that
# are created on upload. Because directories and files share one
# namespace on disk, a key colliding with a stored object is rejected
# instead of being flattened into a single filename.


async def load_bucket(
    repo: ORMRepository,
    bucket_name: str,
    user: User,
    resource: str,
) -> Bucket:
    """
    Load the bucket addressed by an object operation and authorize the
    caller against it (ADR-21): the owner and root are allowed.
    """
    bucket = await repo.select(Bucket, bucket_name=bucket_name)

    if bucket is None:
        raise S3BucketNotFoundError(resource)
    if not user.is_root and bucket.user_id != user.id:
        raise S3AccessDeniedError(resource)

    return bucket


def resolve_object_path(
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


async def assert_bucket_dir(bucket_path: str, resource: str) -> None:
    """
    Ensure the bucket directory backing the bucket row still exists.
    """
    if not await isdir(bucket_path):
        raise S3BucketNotFoundError(resource)


async def mkdir_object_parent(object_path: str, resource: str) -> None:
    """
    Create the directories carrying the key prefix. A prefix occupied
    by a stored object cannot become a directory, and neither can a
    key already used by a directory hold an object.
    """
    if await isdir(object_path):
        raise S3ObjektKeyConflictError(resource)

    try:
        await mkdir(os.path.dirname(object_path))
    except (FileExistsError, NotADirectoryError) as exc:
        raise S3ObjektKeyConflictError(resource) from exc


async def upsert_objekt(
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
