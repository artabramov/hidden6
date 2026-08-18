# app/services/bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy.ext.asyncio import AsyncSession

from app.hooks import Events, hooks
from app.models.bucket import S3Bucket
from app.models.user import User
from app.repositories.orm import ORMRepository


async def bucket_list(
    session: AsyncSession,
    current_user: User,
) -> list[S3Bucket]:
    """
    List S3 buckets visible to the authenticated user.

    Returns all buckets for the root user and only owned buckets
    for other users, ordered by bucket name.
    """
    filters = {
        "order_by": "bucket_name",
        "order": "asc",
    }

    if not current_user.is_root:
        filters["user_id"] = current_user.id

    repo = ORMRepository(session)
    buckets = await repo.select_all(S3Bucket, **filters)

    await hooks.emit(Events.BUCKET_LISTED, buckets)
    return buckets
