# app/services/bucket_versioning_put.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.versioning import set_bucket_versioning_status

log = logging.getLogger(__name__)


async def bucket_versioning_put(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    versioning_status: str,
) -> None:
    """
    Set the S3 versioning state for a bucket.
    """
    resource = f"/{bucket_name}"

    repo = ORMRepository(session)
    bucket = await load_bucket(
        repo,
        bucket_name,
        current_user,
        resource,
    )

    set_bucket_versioning_status(
        bucket,
        versioning_status,
        resource,
    )

    try:
        await repo.update(bucket)
        await repo.commit()

    except Exception:
        try:
            await repo.rollback()
        except Exception:
            log.exception(
                "msg=rollback_failed "
                "bucket_name=%s",
                bucket_name,
            )

        raise
