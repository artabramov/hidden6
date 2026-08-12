# app/services/bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.hooks import hooks, Events
from app.models.bucket import Bucket
from app.models.user import User
from app.repositories.orm import ORMRepository

log = logging.getLogger(__name__)


async def bucket_list(
    user: User,
    session: AsyncSession,
) -> list[Bucket]:
    """
    List buckets visible to the authenticated user. Root user
    sees all buckets; other users see only their own buckets.
    """
    log.info("msg=bucket_list_started user_id=%s", user.id)

    repo = ORMRepository(session)
    filters: dict[str, object] = {
        "order_by": "bucket_name",
        "order": "asc",
    }
    if not user.is_root:
        filters["user_id"] = user.id

    buckets = await repo.select_all(Bucket, **filters)

    log.info("msg=bucket_list_completed count=%d", len(buckets))
    await hooks.emit(Events.BUCKET_LISTED, buckets)

    return buckets
