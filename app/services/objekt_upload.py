# app/services/objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT
from app.errors import S3BucketNotFoundError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.file import (
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
from app.s3.objekt_mkdir import objekt_mkdir
from app.s3.objekt_path import objekt_path
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
    log.info("msg=objekt_upload bucket=%s key=%s", bucket_name, object_key)

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)

    bucket_path = os.path.join(config.MOUNTPOINT_BUCKETS_DIR, bucket_name)
    object_path = objekt_path(bucket_path, object_key, resource)
    staged_path = os.path.join(config.MOUNTPOINT_TMP_DIR, uuid.uuid4().hex)

    try:
        await upload(body, staged_path)
        size_bytes = await get_filesize(staged_path)
        etag = await get_file_hash(staged_path)
        content_type = await get_mimetype(staged_path)

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
            await rename(staged_path, object_path)
            await repo.commit()

    except Exception:
        await repo.rollback()
        await delete(staged_path)
        raise

    log.info("msg=objekt_uploaded bucket=%s key=%s", bucket_name, object_key)
    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)

    return objekt
