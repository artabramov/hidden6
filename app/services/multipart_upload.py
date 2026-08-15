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
    isfile,
    rename,
    upload,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.multipart import multipart_load, multipart_part_upsert
from app.s3.paths import resolve_multipart_part_path, multipart_path
from app.s3.validation import validate_objekt_key

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
    row is written only after the final part file exists. A re-upload
    keeps the previous part file until the database update commits.
    """
    log.info("msg=multipart_upload upload_id=%s part=%d", upload_id, part_number)  # noqa: E501

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    validate_objekt_key(object_key, resource)

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

    upload_dir = multipart_path(config.MOUNTPOINT_TMP_DIR, upload_id)
    part = resolve_multipart_part_path(upload_dir, part_number)

    if not await isdir(upload_dir):
        raise S3ObjektUploadNotFoundError(resource)

    # Serialize re-uploads of the same part number. Different part
    # numbers use different paths and may proceed in parallel.
    async with locks.lock_file(part, LockType.WRITE):
        token = uuid.uuid4().hex
        temp_part = os.path.join(
            upload_dir,
            f".{part_number}.{token}.part.tmp",
        )
        backup_part = None
        published = False

        try:
            await upload(body, temp_part)
            etag = await get_file_hash(temp_part)
            size_bytes = await get_filesize(temp_part)

            # Re-upload: move the previous bytes aside so a failed DB
            # commit can restore them. First upload publishes directly.
            if await isfile(part):
                backup_part = os.path.join(
                    upload_dir,
                    f".{part_number}.{token}.part.bak",
                )
                await rename(part, backup_part)

            await rename(temp_part, part)
            published = True
            temp_part = None

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
                if backup_part is not None:
                    try:
                        await rename(backup_part, part)
                        backup_part = None
                    except Exception:
                        log.exception(
                            "msg=multipart_part_integrity_failed "
                            "part=%s backup=%s",
                            part,
                            backup_part,
                        )
                raise

            if backup_part is not None:
                try:
                    await delete(backup_part)
                except Exception:
                    log.exception(
                        "msg=multipart_part_backup_cleanup_failed "
                        "backup=%s",
                        backup_part,
                    )
                backup_part = None

        except Exception:
            if temp_part is not None:
                await delete(temp_part)
            # Restore previous bytes only when the new part never became
            # the published file. After a published re-upload, restore
            # is handled above around the DB commit.
            if not published and backup_part is not None:
                try:
                    await rename(backup_part, part)
                except Exception:
                    log.exception(
                        "msg=multipart_part_integrity_failed "
                        "part=%s backup=%s",
                        part,
                        backup_part,
                    )
            raise

    log.info("msg=multipart_uploaded upload_id=%s part=%d", upload_id, part_number)  # noqa: E501
    return etag
