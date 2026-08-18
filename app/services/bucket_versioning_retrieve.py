# app/services/bucket_versioning_retrieve.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.versioning import get_bucket_versioning_status


async def bucket_versioning_retrieve(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
) -> str | None:
    """
    Return the S3 versioning status configured for a bucket.

    A bucket where versioning has never been configured returns no
    Status value.
    """
    resource = f"/{bucket_name}"

    repo = ORMRepository(session)
    bucket = await load_bucket(
        repo,
        bucket_name,
        current_user,
        resource,
    )

    return get_bucket_versioning_status(bucket)
