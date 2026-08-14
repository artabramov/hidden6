# app/services/multipart_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_PART_NUMBER_MAX
from app.errors import (
    S3ObjektPartNumberInvalidError,
    S3ObjektUploadNotFoundError,
)
from app.locks import LockType, locks
from app.models.user import User
from app.repositories.io import (
    AsyncReadable,
    delete,
    get_file_hash,
    get_filesize,
    isdir,
    rename,
    upload,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.multipart import multipart_load, multipart_part_upsert
from app.s3.objekt import objekt_key_validate

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
    its ETag. Bytes are staged on disk first; the ObjektMultipartPart
    row is written only after the final part file exists. Uploading the
    same part number again replaces both the staged file and the row.
    """
    log.info("msg=multipart_upload upload_id=%s part=%d", upload_id, part_number)  # noqa: E501

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    objekt_key_validate(object_key, resource)

    if part_number < 1 or part_number > OBJEKT_PART_NUMBER_MAX:
        raise S3ObjektPartNumberInvalidError(resource)

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
    part = os.path.join(upload_dir, f"{part_number}.part")

    if not await isdir(upload_dir):
        raise S3ObjektUploadNotFoundError(resource)

    # Serialize re-uploads of the same part number. Different part
    # numbers use different paths and may proceed in parallel.
    async with locks.lock_file(part, LockType.WRITE):
        temp_part = os.path.join(
            upload_dir,
            f".{part_number}.{uuid.uuid4().hex}.part.tmp",
        )
        try:
            # Stage the body into a temporary file, measure it, then
            # publish the final part path. A failed upload leaves any
            # previously published part file in place.
            await upload(body, temp_part)
            etag = await get_file_hash(temp_part)
            size_bytes = await get_filesize(temp_part)
            await rename(temp_part, part)
        except Exception:
            await delete(temp_part)
            raise

        # Index the part only after the final file exists. A failed
        # commit leaves an orphan staged file rather than a row that
        # points at missing bytes.
        try:
            await multipart_part_upsert(
                repo=repo,
                multipart=multipart,
                part_number=part_number,
                size_bytes=size_bytes,
                etag=etag,
            )
        except Exception:
            await repo.rollback()
            raise

    log.info("msg=multipart_uploaded upload_id=%s part=%d", upload_id, part_number)  # noqa: E501
    return etag
