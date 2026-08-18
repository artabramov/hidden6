# app/services/multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.locks import LockType, locks
from app.models.user import User
from app.repositories.io import isdir, rename, rmtree
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.multipart import load_multipart, delete_multipart_parts
from app.s3.paths import (
    resolve_multipart_aborted_path,
    resolve_multipart_path,
)
from app.s3.validation import validate_object_key

log = logging.getLogger(__name__)


async def multipart_abort(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    object_key: str,
    upload_id: str,
) -> None:
    """
    Abort an S3 multipart upload. The operation is transactional at
    the DB level and reconciles filesystem state on failure. The active
    multipart upload directory is moved aside under a directory lock
    before its database state is removed.

    (1) load the multipart upload
    (2) move the active upload directory to a temporary cleanup path
    (3) delete all multipart part records
    (4) delete the multipart upload record
    (5) commit

    On failure of the transaction, the session is rolled back and the
    active multipart upload directory is restored from the temporary
    cleanup path when it was moved.

    After a successful commit, the temporary cleanup directory and all
    stored part data are removed as a best-effort cleanup step.
    """
    config = get_config()
    resource = f"/{bucket_name}/{object_key}"

    validate_object_key(object_key, resource)

    repo = ORMRepository(session)
    bucket = await load_bucket(repo, bucket_name, current_user, resource)

    # Path containing the active multipart upload
    # and its uploaded parts.
    upload_path = resolve_multipart_path(
        config.MOUNTPOINT_TMP_DIR,
        upload_id,
    )

    # Temporary path used to move the multipart upload
    # aside until the abort transaction is committed.
    cleanup_path = resolve_multipart_aborted_path(
        config.MOUNTPOINT_TMP_DIR,
        upload_id,
        uuid.uuid4().hex,
    )

    upload_moved = False

    async with locks.lock_directory(upload_path, LockType.WRITE):
        try:
            multipart = await load_multipart(
                repo=repo,
                bucket=bucket,
                object_key=object_key,
                upload_id=upload_id,
                resource=resource,
            )

            # Move the active upload aside before deleting its DB state
            # so concurrent UploadPart requests cannot publish new parts
            # into it.
            if await isdir(upload_path):
                await rename(upload_path, cleanup_path)
                upload_moved = True

            await delete_multipart_parts(repo, multipart)
            await repo.delete(multipart)
            await repo.commit()

        # Roll back DB state and restore the active upload directory
        # before releasing the lock, so no UploadPart request can
        # observe an intermediate state.
        except Exception:
            try:
                await repo.rollback()
            except Exception:
                log.exception(
                    "msg=rollback_failed "
                    "bucket_name=%s "
                    "object_key=%s "
                    "upload_id=%s",
                    bucket_name,
                    object_key,
                    upload_id,
                )

            if upload_moved:
                try:
                    await rename(cleanup_path, upload_path)
                    upload_moved = False
                except Exception:
                    log.exception(
                        "msg=restore_failed "
                        "upload_path=%s "
                        "cleanup_path=%s",
                        upload_path,
                        cleanup_path,
                    )
            raise

    # After a successful commit, the aborted multipart
    # upload directory is no longer needed.
    if upload_moved:
        try:
            await rmtree(cleanup_path)
        except OSError:
            log.exception(
                "msg=cleanup_failed "
                "cleanup_path=%s",
                cleanup_path,
            )
