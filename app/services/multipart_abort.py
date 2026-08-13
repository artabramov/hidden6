# app/services/multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.locks import LockType, locks
from app.models.user import User
from app.repositories.io import rmtree
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.multipart import multipart_load
from app.s3.objekt_key_validate import objekt_key_validate

log = logging.getLogger(__name__)


async def multipart_abort(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    upload_id: str,
) -> None:
    """
    Abort a multipart upload (S3 AbortMultipartUpload): drop the
    upload together with every part staged for it.
    """
    log.info("msg=multipart_abort upload_id=%s", upload_id)

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    objekt_key_validate(object_key, resource)

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)
    multipart = await multipart_load(
        repo=repo,
        bucket=bucket,
        object_key=object_key,
        upload_id=upload_id,
        resource=resource,
    )

    await repo.delete(multipart, commit=True)
    upload_dir = os.path.join(config.MOUNTPOINT_TMP_DIR, upload_id)

    # The upload is already dropped, so parts left behind by a failed
    # cleanup are logged instead of failing the request. The lock keeps
    # the cleanup from pulling the parts out from under an assembly or
    # a part upload that is already running.
    try:
        async with locks.lock_directory(upload_dir, LockType.WRITE):
            await rmtree(upload_dir)
    except OSError:
        log.exception("msg=multipart_cleanup_failed path=%s", upload_dir)

    log.info("msg=multipart_aborted upload_id=%s", upload_id)
