# app/services/objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT
from app.errors import S3BucketNotFoundError, S3ObjektKeyConflictError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import (
    AsyncReadable,
    delete,
    get_file_hash,
    get_filesize,
    get_mimetype,
    isdir,
    rename,
    upload,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket_load import bucket_load
from app.s3.objekt_dir import objekt_dir
from app.s3.objekt_mkdir import objekt_mkdir
from app.s3.objekt_upsert import objekt_upsert

log = logging.getLogger(__name__)


async def objekt_upload(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    body: AsyncReadable,
) -> Objekt:
    """
    Upload an S3 object to the specified bucket.

    Stages the object data in the temporary directory, creates the
    required key directories, stores the object in the bucket, and
    creates or updates its metadata. An existing object with the
    same key is overwritten and assigned to the current user.
    """
    config = get_config()
    resource = f"/{bucket_name}/{object_key}"

    bucket_path, object_path = objekt_dir(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        object_key,
        resource,
    )

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)

    staged_path = os.path.join(config.MOUNTPOINT_TMP_DIR, uuid.uuid4().hex)

    try:
        await upload(body, staged_path)
        size_bytes = await get_filesize(staged_path)
        etag = await get_file_hash(staged_path)
        content_type = await get_mimetype(staged_path)

        # The body is already staged, so the lock guards publishing
        # alone: between the key conflict check and the rename that
        # makes the object visible no other task may occupy the object
        # path with a directory, or a prefix of the key with an object.
        # The whole bucket subtree is locked because a conflicting key
        # can sit at any prefix level.
        async with locks.lock_directory(bucket_path, LockType.WRITE):
            if not await isdir(bucket_path):
                raise S3BucketNotFoundError(resource)

            await objekt_mkdir(object_path, resource)

            objekt = await objekt_upsert(
                repo=repo,
                bucket=bucket,
                user=user,
                object_key=object_key,
                size_bytes=size_bytes,
                etag=etag,
                content_type=content_type or OBJEKT_CONTENT_TYPE_DEFAULT,
            )

            # The conflict check above already rejected a directory at
            # the object path, but the lock covers requests only: a
            # change made straight on the mount can still put one there
            # before the rename lands.
            try:
                await rename(staged_path, object_path)
            except (IsADirectoryError, NotADirectoryError) as exc:
                raise S3ObjektKeyConflictError(resource) from exc

            await repo.commit()

    except Exception:
        await repo.rollback()
        await delete(staged_path)
        raise

    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)
    return objekt
