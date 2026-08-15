# app/services/multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.locks import LockType, locks
from app.models.user import User
from app.repositories.io import isdir, rename, rmtree
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.multipart import multipart_load, multipart_parts_delete
from app.s3.paths import resolve_multipart_path
from app.s3.validation import validate_objekt_key

log = logging.getLogger(__name__)


async def multipart_abort(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    objekt_key: str,
    upload_id: str,
) -> None:
    """
    Abort a multipart upload (S3 AbortMultipartUpload): move the
    staging directory aside, drop every ObjektMultipartPart row and the
    parent upload, then remove the renamed directory. A failed commit
    restores the active upload directory when possible.
    """
    log.info("msg=multipart_abort upload_id=%s", upload_id)

    config = get_config()
    resource = f"/{bucket_name}/{objekt_key}"
    validate_objekt_key(objekt_key, resource)

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, current_user, resource)
    multipart = await multipart_load(
        repo=repo,
        bucket=bucket,
        object_key=objekt_key,
        upload_id=upload_id,
        resource=resource,
    )

    upload_dir = resolve_multipart_path(config.MOUNTPOINT_TMP_DIR, upload_id)
    cleanup_dir = None

    try:
        async with locks.lock_directory(upload_dir, LockType.WRITE):
            # Rename first so concurrent UploadPart cannot publish into
            # the active path after the DB rows are gone.
            if await isdir(upload_dir):
                cleanup_dir = os.path.join(
                    config.MOUNTPOINT_TMP_DIR,
                    f".{upload_id}.aborted.{uuid.uuid4().hex}",
                )
                await rename(upload_dir, cleanup_dir)

            await multipart_parts_delete(repo, multipart)
            await repo.delete(multipart)
            await repo.commit()

    except Exception:
        await repo.rollback()
        if cleanup_dir is not None:
            try:
                await rename(cleanup_dir, upload_dir)
                cleanup_dir = None
            except Exception:
                log.exception(
                    "msg=multipart_abort_integrity_failed "
                    "upload_dir=%s cleanup=%s",
                    upload_dir,
                    cleanup_dir,
                )
        raise

    if cleanup_dir is not None:
        try:
            await rmtree(cleanup_dir)
        except OSError:
            log.exception(
                "msg=multipart_cleanup_failed path=%s",
                cleanup_dir,
            )

    log.info("msg=multipart_aborted upload_id=%s", upload_id)
