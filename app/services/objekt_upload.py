# app/services/objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT
from app.errors import (
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3ObjektKeyConflictError,
    S3ObjektKeyInvalidError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.bucket import Bucket
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.file import (
    AsyncReadable,
    delete,
    get_file_hash,
    get_filesize,
    get_mimetype,
    isdir,
    mkdir,
    rename,
    upload,
)
from app.repositories.orm import ORMRepository

log = logging.getLogger(__name__)

# NOTE (ADR-24): S3 object keys map to nested filesystem paths.
# A key is stored as a path relative to the bucket directory, so the
# key photos/2024/cat.png becomes a file in nested directories that
# are created on upload. Because directories and files share one
# namespace on disk, a key colliding with a stored object is rejected
# instead of being flattened into a single filename.


async def objekt_upload(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    body: AsyncReadable,
) -> Objekt:
    """
    Upload an object into a bucket: stage the body in the mountpoint
    tmp dir, publish it under the bucket directory, and upsert the
    Objekt row. Overwriting a key replaces the stored bytes and makes
    the caller its uploader. object_key must already be validated
    (ObjektUploadRequest).
    """
    log.info(
        "msg=objekt_upload_started bucket=%s key=%s",
        bucket_name,
        object_key,
    )

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    repo = ORMRepository(session)

    bucket = await repo.select(Bucket, bucket_name=bucket_name)
    if bucket is None:
        raise S3BucketNotFoundError(resource)
    if not user.is_root and bucket.user_id != user.id:
        raise S3AccessDeniedError(resource)

    bucket_path = os.path.join(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
    )
    object_path = _resolve_object_path(bucket_path, object_key, resource)
    staged_path = os.path.join(
        config.MOUNTPOINT_TMP_DIR,
        uuid.uuid4().hex,
    )

    try:
        await upload(body, staged_path)
        size_bytes = await get_filesize(staged_path)
        etag = await get_file_hash(staged_path)
        content_type = await get_mimetype(staged_path)

        async with locks.lock_directory(bucket_path, LockType.WRITE):
            if not await isdir(bucket_path):
                raise S3BucketNotFoundError(resource)
            if await isdir(object_path):
                raise S3ObjektKeyConflictError(resource)

            await _mkdir_object_parent(object_path, resource)

            objekt = await _upsert_objekt(
                repo=repo,
                bucket=bucket,
                user=user,
                object_key=object_key,
                size_bytes=size_bytes,
                etag=etag,
                content_type=content_type or OBJEKT_CONTENT_TYPE_DEFAULT,
            )
            await rename(staged_path, object_path)
            await repo.commit()

    except Exception:
        await repo.rollback()
        await delete(staged_path)
        raise

    log.info(
        "msg=objekt_uploaded bucket=%s key=%s size=%d",
        bucket_name,
        object_key,
        size_bytes,
    )
    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)

    return objekt


def _resolve_object_path(
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


async def _mkdir_object_parent(object_path: str, resource: str) -> None:
    """
    Create the directories carrying the key prefix. A prefix occupied
    by a stored object cannot become a directory.
    """
    try:
        await mkdir(os.path.dirname(object_path))
    except (FileExistsError, NotADirectoryError) as exc:
        raise S3ObjektKeyConflictError(resource) from exc


async def _upsert_objekt(
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
