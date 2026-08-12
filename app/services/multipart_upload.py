# app/services/multipart_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

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
from app.services.multipart_store import (
    load_multipart,
    part_path,
    upload_dir,
)

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
    log.info(
        "msg=multipart_upload_started upload_id=%s part=%d",
        upload_id,
        part_number,
    )

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"

    if part_number < 1 or part_number > OBJEKT_PART_NUMBER_MAX:
        raise S3ObjektPartNumberInvalidError(resource)

    repo = ORMRepository(session)
    await load_multipart(
        repo=repo,
        bucket_name=bucket_name,
        object_key=object_key,
        user=user,
        upload_id=upload_id,
        resource=resource,
    )

    upload_dir_path = upload_dir(config.MOUNTPOINT_TMP_DIR, upload_id)
    part = part_path(upload_dir_path, part_number)

    if not await isdir(upload_dir_path):
        raise S3ObjektUploadNotFoundError(resource)

    # A failed upload leaves the part that was stored before in place,
    # because the body is staged and only then replaces the part file.
    async with locks.lock_file(part, LockType.WRITE):
        await upload(body, part)
        etag = await get_file_hash(part)

    log.info(
        "msg=multipart_uploaded upload_id=%s part=%d",
        upload_id,
        part_number,
    )

    return etag
