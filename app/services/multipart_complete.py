# app/services/multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT
from app.errors import S3BucketNotFoundError, S3ObjektPartInvalidError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.file import (
    concat,
    delete,
    get_filesize,
    get_mimetype,
    isdir,
    rename,
    rmtree,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket_dir import bucket_dir
from app.s3.bucket_load import bucket_load
from app.s3.etag_construct import etag_construct
from app.s3.multipart_load import multipart_load
from app.s3.multipart_parts import multipart_parts
from app.s3.objekt_key_validate import objekt_key_validate
from app.s3.objekt_mkdir import objekt_mkdir
from app.s3.objekt_path import objekt_path
from app.s3.objekt_upsert import objekt_upsert
from app.schemas.multipart_complete import MultipartPart

log = logging.getLogger(__name__)


async def multipart_complete(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    upload_id: str,
    parts: list[MultipartPart],
) -> Objekt:
    """
    Assemble the uploaded parts into a single object (S3
    CompleteMultipartUpload): concatenate the parts listed by the
    client, publish the result under the bucket directory, upsert the
    Objekt row, and drop the upload with its staged parts.
    """
    log.info("msg=multipart_complete upload_id=%s parts=%d", upload_id, len(parts))  # noqa: E501

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    objekt_key_validate(object_key, resource)
    bucket_path = bucket_dir(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        resource,
    )

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)

    multipart = await multipart_load(
        repo=repo,
        bucket=bucket,
        object_key=object_key,
        upload_id=upload_id,
        resource=resource,
    )

    upload_dir = os.path.join(config.MOUNTPOINT_TMP_DIR, upload_id)
    object_path = objekt_path(bucket_path, object_key, resource)
    staged_path = os.path.join(config.MOUNTPOINT_TMP_DIR, uuid.uuid4().hex)

    try:
        # The lock keeps an abort or a part upload from changing the
        # parts between their validation and the assembly. A part
        # replaced before the lock was taken is still caught by the
        # ETag comparison below.
        async with locks.lock_directory(upload_dir, LockType.READ):
            part_paths = await multipart_parts(upload_dir, parts, resource)
            part_hashes = await concat(part_paths, staged_path)

        for part, part_hash in zip(parts, part_hashes):
            if part.etag != part_hash:
                raise S3ObjektPartInvalidError(resource)

        size_bytes = await get_filesize(staged_path)
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
                etag=etag_construct(part_hashes),
                content_type=content_type or OBJEKT_CONTENT_TYPE_DEFAULT,
            )
            await repo.delete(multipart)
            await rename(staged_path, object_path)
            await repo.commit()

    except Exception:
        await repo.rollback()
        await delete(staged_path)
        raise

    # The upload is already finished, so parts left behind by a failed
    # cleanup are logged instead of failing the request.
    try:
        await rmtree(upload_dir)
    except OSError:
        log.exception("msg=multipart_cleanup_failed path=%s", upload_dir)

    log.info("msg=multipart_completed bucket=%s key=%s", bucket_name, object_key)  # noqa: E501
    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)

    return objekt
