# app/services/bucket_create.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.errors import (
    S3BucketAlreadyExistsError,
    S3BucketAlreadyOwnedByYouError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.bucket import Bucket
from app.models.user import User
from app.repositories.file import isdir, mkdir, rmdir
from app.repositories.orm import ORMRepository

log = logging.getLogger(__name__)


async def bucket_create(
    bucket_name: str,
    user: User,
    session: AsyncSession,
) -> Bucket:
    """
    Create an S3 bucket: mkdir under the mountpoint buckets dir and
    insert the Bucket row owned by the caller. bucket_name must already
    be validated (BucketCreateRequest).
    """
    log.info("msg=bucket_create_started bucket=%s", bucket_name)

    config = get_config()
    resource = f"/{bucket_name}"
    bucket_path = os.path.join(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
    )

    async with locks.lock_directory(
        bucket_path,
        LockType.WRITE,
    ):
        repo = ORMRepository(session)
        existing = await repo.select(Bucket, bucket_name=bucket_name)
        if existing is not None:
            if existing.user_id == user.id:
                raise S3BucketAlreadyOwnedByYouError(resource)
            raise S3BucketAlreadyExistsError(resource)

        if await isdir(bucket_path):
            log.warning(
                "msg=bucket_create_orphan_dir bucket=%s",
                bucket_name,
            )
            raise S3BucketAlreadyExistsError(resource)

        await mkdir(bucket_path)

        bucket = Bucket(
            user_id=user.id,
            bucket_name=bucket_name,
        )
        try:
            await repo.insert(bucket, commit=True)
        except Exception:
            if await isdir(bucket_path):
                await rmdir(bucket_path)
            raise

    log.info("msg=bucket_created bucket=%s", bucket_name)
    await hooks.emit(Events.BUCKET_CREATED, bucket)

    return bucket
