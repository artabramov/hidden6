# app/services/objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT
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
    rename,
    upload,
)
from app.repositories.orm import ORMRepository
from app.services.objekt_store import (
    assert_bucket_dir,
    load_bucket,
    mkdir_object_parent,
    resolve_object_path,
    upsert_objekt,
)

log = logging.getLogger(__name__)


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
    bucket = await load_bucket(repo, bucket_name, user, resource)

    bucket_path = os.path.join(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
    )
    object_path = resolve_object_path(bucket_path, object_key, resource)
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
            await assert_bucket_dir(bucket_path, resource)
            await mkdir_object_parent(object_path, resource)

            objekt = await upsert_objekt(
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
