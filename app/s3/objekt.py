# app/s3/objekt.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import time

from app.errors import (
    S3ObjektKeyConflictError,
    S3ObjektNotFoundError,
)
from app.models.bucket import Bucket
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import isdir, mktree
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_default_object_lock


async def objekt_load(
    repo: ORMRepository,
    bucket: Bucket,
    object_key: str,
    resource: str,
) -> Objekt:
    """
    Load the Objekt row for a key inside a bucket. A missing row or a
    current delete marker is reported as NoSuchKey — the same code S3
    uses when GetObject / HeadObject address a key with no current
    object bytes.
    """
    objekt = await repo.select(
        Objekt,
        bucket_id=bucket.id,
        object_key=object_key,
    )

    if objekt is None or objekt.delete_marker:
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
    the key is overwritten. The current state becomes an object with a
    payload (not a delete marker). Bucket default Object Lock retention
    is applied to the new current state. Changes are flushed, not
    committed.
    """
    lock_mode, retain_until = bucket_default_object_lock(bucket)

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
            delete_marker=False,
            lock_mode=lock_mode,
            retain_until=retain_until,
        )
        return await repo.insert(objekt)

    objekt.user_id = user.id
    objekt.size_bytes = size_bytes
    objekt.etag = etag
    objekt.content_type = content_type
    objekt.delete_marker = False
    objekt.lock_mode = lock_mode
    objekt.retain_until = retain_until
    objekt.legal_hold = False
    objekt.modified_at = int(time.time())

    return await repo.update(objekt)
