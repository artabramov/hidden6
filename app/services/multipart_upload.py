# app/services/multipart_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_PART_NUMBER_MAX
from app.errors import (
    S3ObjektPartNumberInvalidError,
    S3ObjektUploadNotFoundError,
)
from app.locks import LockType, locks
from app.models.user import User
from app.repositories.file import (
    AsyncReadable,
    get_file_hash,
    isdir,
    upload,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket_load import bucket_load
from app.s3.multipart_load import multipart_load
from app.s3.objekt_key_validate import objekt_key_validate

log = logging.getLogger(__name__)


async def multipart_upload(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    upload_id: str,
    part_number: int,
    body: AsyncReadable,
) -> str:
    """
    Store one part of a multipart upload (S3 UploadPart) and return
    its ETag. Uploading the same part number again replaces the part
    that was stored before.
    """
    log.info("msg=multipart_upload upload_id=%s part=%d", upload_id, part_number)  # noqa: E501

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    objekt_key_validate(object_key, resource)

    if part_number < 1 or part_number > OBJEKT_PART_NUMBER_MAX:
        raise S3ObjektPartNumberInvalidError(resource)

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)

    await multipart_load(
        repo=repo,
        bucket=bucket,
        object_key=object_key,
        upload_id=upload_id,
        resource=resource,
    )

    upload_dir = os.path.join(config.MOUNTPOINT_TMP_DIR, upload_id)
    part = os.path.join(upload_dir, f"{part_number}.part")

    if not await isdir(upload_dir):
        raise S3ObjektUploadNotFoundError(resource)

    # A failed upload leaves the part that was stored before in place,
    # because the body is staged and only then replaces the part file.
    async with locks.lock_file(part, LockType.WRITE):
        await upload(body, part)
        etag = await get_file_hash(part)

    log.info("msg=multipart_uploaded upload_id=%s part=%d", upload_id, part_number)  # noqa: E501
    return etag
