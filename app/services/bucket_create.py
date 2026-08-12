# app/services/bucket_create.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

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
from app.repositories.file import isdir, isfile, mktree, rmdir
from app.repositories.orm import ORMRepository
from app.s3.bucket_dir import bucket_dir

log = logging.getLogger(__name__)


async def bucket_create(
    bucket_name: str,
    user: User,
    session: AsyncSession,
) -> Bucket:
    """
    Create an S3 bucket for the specified user.

    Reserves the bucket name in the database, creates the bucket
    directory, and commits the transaction. If the operation fails
    after the directory is created, the transaction is rolled back
    and the directory is removed.
    """
    cfg = get_config()

    resource = f"/{bucket_name}"
    bucket_path = bucket_dir(cfg.MOUNTPOINT_BUCKETS_DIR, bucket_name, resource)

    async with locks.lock_directory(bucket_path, LockType.WRITE):
        repo = ORMRepository(session)
        existing = await repo.select(Bucket, bucket_name=bucket_name)

        if existing is not None:
            if existing.user_id == user.id:
                raise S3BucketAlreadyOwnedByYouError(resource)

            raise S3BucketAlreadyExistsError(resource)

        if await isdir(bucket_path):
            raise S3BucketAlreadyExistsError(resource)

        if await isfile(bucket_path):
            raise S3BucketAlreadyExistsError(resource)

        try:
            directory_created = False

            bucket = Bucket(user_id=user.id, bucket_name=bucket_name)
            await repo.insert(bucket)

            await mktree(bucket_path)
            directory_created = True

            await repo.commit()

        except Exception:
            await repo.rollback()

            if directory_created:
                try:
                    await rmdir(bucket_path)
                except Exception:
                    log.exception("msg=cleanup_failed bucket=%s", bucket_name)

            raise

    await hooks.emit(Events.BUCKET_CREATED, bucket)
    return bucket
