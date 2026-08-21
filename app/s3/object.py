# app/s3/object.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import time

from app.errors import (
    S3ObjectKeyConflictError,
    S3ObjectNotFoundError,
)
from app.models.bucket import S3Bucket
from app.models.object import S3Object
from app.models.object_version import S3ObjectVersion
from app.models.user import User
from app.repositories.io import isdir, mktree
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_default_object_lock


async def load_object(
    repo: ORMRepository,
    bucket: S3Bucket,
    object_key: str,
    resource: str,
) -> S3Object:
    """
    Load the S3Object row for a key inside a bucket. A missing row or a
    current delete marker is reported as NoSuchKey — the same code S3
    uses when GetObject / HeadObject address a key with no current
    object bytes.
    """
    s3_object = await repo.select(
        S3Object,
        bucket_id=bucket.id,
        object_key=object_key,
    )

    if s3_object is None or s3_object.delete_marker:
        raise S3ObjectNotFoundError(resource)

    return s3_object


async def object_mkdir(object_path: str, resource: str) -> None:
    """
    Create the directories carrying the key prefix. A prefix occupied
    by a stored object cannot become a directory, and neither can a
    key already used by a directory hold an object.
    """
    if await isdir(object_path):
        raise S3ObjectKeyConflictError(resource)

    try:
        await mktree(os.path.dirname(object_path))
    except (FileExistsError, NotADirectoryError) as exc:
        raise S3ObjectKeyConflictError(resource) from exc


async def upsert_object(
    repo: ORMRepository,
    bucket: S3Bucket,
    user: User,
    object_key: str,
    size_bytes: int,
    etag: str,
    content_type: str,
    version_uuid: str | None,
) -> S3Object:
    """
    Insert the S3Object row for a new key or update the existing row
    when the key is overwritten. The current state becomes an object
    with a payload (not a delete marker). Bucket default object lock
    retention is applied to the new current state.
    """
    lock_mode, retain_until = bucket_default_object_lock(bucket)

    s3_object = await repo.select(
        S3Object,
        bucket_id=bucket.id,
        object_key=object_key,
    )

    if s3_object is None:
        s3_object = S3Object(
            bucket_id=bucket.id,
            user_id=user.id,
            object_key=object_key,
            size_bytes=size_bytes,
            etag=etag,
            content_type=content_type,
            version_uuid=version_uuid,
            delete_marker=False,
            lock_mode=lock_mode,
            retain_until=retain_until,
        )
        return await repo.insert(s3_object)

    s3_object.user_id = user.id
    s3_object.modified_at = int(time.time())
    s3_object.size_bytes = size_bytes
    s3_object.etag = etag
    s3_object.content_type = content_type
    s3_object.version_uuid = version_uuid
    s3_object.delete_marker = False
    s3_object.lock_mode = lock_mode
    s3_object.retain_until = retain_until
    s3_object.legal_hold = False

    return await repo.update(s3_object)


async def create_object_version(
    repo: ORMRepository,
    s3_object: S3Object,
) -> S3ObjectVersion:
    """
    Preserve the current object state as a noncurrent version.

    The returned row is flushed so its internal ID can be used
    to address the retained payload in version storage.
    """
    version = S3ObjectVersion(
        object_id=s3_object.id,
        user_id=s3_object.user_id,
        modified_at=s3_object.modified_at,
        version_uuid=s3_object.version_uuid,
        size_bytes=s3_object.size_bytes,
        etag=s3_object.etag,
        content_type=s3_object.content_type,
        delete_marker=s3_object.delete_marker,
        lock_mode=s3_object.lock_mode,
        retain_until=s3_object.retain_until,
        legal_hold=s3_object.legal_hold,
    )

    return await repo.insert(version)
