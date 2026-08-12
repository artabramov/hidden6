# app/services/multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.multipart_cleanup import multipart_cleanup
from app.s3.multipart_load import multipart_load

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
    log.info("msg=multipart_abort_started upload_id=%s", upload_id)

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    repo = ORMRepository(session)
    multipart = await multipart_load(
        repo=repo,
        bucket_name=bucket_name,
        object_key=object_key,
        user=user,
        upload_id=upload_id,
        resource=resource,
    )

    await repo.delete(multipart, commit=True)
    await multipart_cleanup(
        os.path.join(config.MOUNTPOINT_TMP_DIR, upload_id),
    )

    log.info("msg=multipart_aborted upload_id=%s", upload_id)
