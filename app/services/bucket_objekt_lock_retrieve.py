# app/services/bucket_objekt_lock_retrieve.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import S3ObjectLockConfigurationNotFoundError
from app.hooks import Events, hooks
from app.models.bucket import Bucket
from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket


async def bucket_objekt_lock_retrieve(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
) -> Bucket:
    """
    Retrieve the S3 Object Lock configuration for a bucket.

    Raises:
        S3ObjectLockConfigurationNotFoundError:
            Object Lock is not enabled for the bucket.
    """
    resource = f"/{bucket_name}"

    repo = ORMRepository(session)
    bucket = await load_bucket(
        repo,
        bucket_name,
        current_user,
        resource,
    )

    if not bucket.object_lock_enabled:
        raise S3ObjectLockConfigurationNotFoundError(resource)

    await hooks.emit(Events.BUCKET_OBJEKT_LOCK_RETRIEVED, bucket)
    return bucket
