# app/services/multipart_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_PART_NUMBER_MAX
from app.errors import (
    S3ObjectPartNumberInvalidError,
    S3ObjectUploadNotFoundError,
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
from app.s3.bucket import load_bucket
from app.s3.multipart import load_multipart, upsert_multipart_part
from app.s3.paths import (
    resolve_multipart_backup_part_path,
    resolve_multipart_part_path,
    resolve_multipart_path,
    resolve_multipart_staged_part_path,
)
from app.s3.validation import validate_objekt_key

log = logging.getLogger(__name__)


async def multipart_upload(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    objekt_key: str,
    upload_id: str,
    part_number: int,
    body: AsyncReadable,
) -> str:
    """
    Upload one part of an S3 multipart upload. The operation is
    transactional at the DB level and reconciles filesystem state
    on failure. Part writes are staged through a temporary file and
    applied under a part-level lock.

    (1) verify that the multipart upload still exists
    (2) upload part data to a temporary path
    (3) read part metadata (size, ETag)

    if part already exists:
        (4) move the current part to a temporary backup

    (5) publish the staged part
    (6) create or update the multipart part record
    (7) commit

    On failure of the transaction, the session is rolled back and
    filesystem state is reconciled: newly written parts are removed,
    previous parts are restored from their temporary backup, and staged
    data is removed.

    After a successful commit, the temporary backup of a replaced part
    is removed as a best-effort cleanup step.
    """
    config = get_config()
    resource = f"/{bucket_name}/{objekt_key}"

    validate_objekt_key(objekt_key, resource)

    if part_number < 1 or part_number > OBJEKT_PART_NUMBER_MAX:
        raise S3ObjectPartNumberInvalidError(resource)

    repo = ORMRepository(session)
    bucket = await load_bucket(repo, bucket_name, current_user, resource)

    upload_path = resolve_multipart_path(config.MOUNTPOINT_TMP_DIR, upload_id)
    part_path = resolve_multipart_part_path(upload_path, part_number)
    token = uuid.uuid4().hex

    # Temporary path used to stage the incoming part
    # before it is published to the multipart upload.
    staged_path = resolve_multipart_staged_part_path(
        upload_path,
        part_number,
        token,
    )

    # Temporary path used to preserve the existing part
    # so it can be restored if the re-upload fails.
    backup_path = resolve_multipart_backup_part_path(
        upload_path,
        part_number,
        token,
    )

    backup_created = False
    part_written = False

    # Serialize re-uploads of the same part number. Different part
    # numbers use different paths and may proceed in parallel.
    async with locks.lock_file(part_path, LockType.WRITE):
        try:
            if not await isdir(upload_path):
                raise S3ObjectUploadNotFoundError(resource)

            multipart = await load_multipart(
                repo=repo,
                bucket=bucket,
                object_key=objekt_key,
                upload_id=upload_id,
                resource=resource,
            )

            await upload(body, staged_path)
            etag = await get_file_hash(staged_path)
            size_bytes = await get_filesize(staged_path)

            # Preserve the current part before overwriting it so
            # a failed transaction can restore the previous payload.
            if await isfile(part_path):
                await rename(part_path, backup_path)
                backup_created = True

            await rename(staged_path, part_path)
            part_written = True

            await upsert_multipart_part(
                repo=repo,
                multipart=multipart,
                part_number=part_number,
                size_bytes=size_bytes,
                etag=etag,
            )
            await repo.commit()

        # Roll back DB state and reconcile the part files before
        # releasing the part lock, so no concurrent re-upload can
        # observe an intermediate state.
        except Exception:
            try:
                await repo.rollback()
            except Exception:
                log.exception(
                    "msg=rollback_failed "
                    "bucket_name=%s "
                    "object_key=%s "
                    "part_number=%s",
                    bucket_name,
                    objekt_key,
                    part_number,
                )

            # A new part was published before the transaction failed.
            # Remove it because there is no previous payload to restore.
            if part_written and not backup_created:
                try:
                    await delete(part_path)
                except Exception:
                    log.exception(
                        "msg=cleanup_failed "
                        "part_path=%s",
                        part_path,
                    )

            # An existing part was moved aside before the transaction
            # failed. Restore it from the temporary backup.
            if backup_created:
                try:
                    await rename(backup_path, part_path)
                except Exception:
                    log.exception(
                        "msg=restore_failed "
                        "part_path=%s "
                        "backup_path=%s",
                        part_path,
                        backup_path,
                    )

            # Remove any staged payload left behind
            # by a failed part upload.
            try:
                await delete(staged_path)
            except Exception:
                log.exception(
                    "msg=cleanup_failed "
                    "staged_path=%s",
                    staged_path,
                )

            raise

        # After a successful commit, the previous part
        # payload is no longer needed.
        if backup_created:
            try:
                await delete(backup_path)
            except Exception:
                log.exception(
                    "msg=cleanup_failed "
                    "backup_path=%s",
                    backup_path,
                )

    return etag
