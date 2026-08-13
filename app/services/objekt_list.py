# app/services/objekt_list.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.hooks import Events, hooks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load

log = logging.getLogger(__name__)


async def objekt_list(
    bucket_name: str,
    user: User,
    session: AsyncSession,
    prefix: str = "",
    max_keys: int = 1000,
) -> list[Objekt]:
    """
    List S3 objects in a bucket visible to the authenticated user.

    Returns objects whose key starts with the given prefix, ordered
    by key, up to max_keys results. The caller is authorized the same
    way as for all other object operations.
    """
    log.info("msg=objekt_list bucket=%s prefix=%r", bucket_name, prefix)

    resource = f"/{bucket_name}"
    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)

    filters: dict = {
        "bucket_id": bucket.id,
        "order_by": "object_key",
        "order": "asc",
        "limit": max_keys,
    }

    if prefix:
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        filters["object_key__like"] = f"{escaped}%"

    objekts = await repo.select_all(Objekt, **filters)

    await hooks.emit(Events.OBJEKT_LISTED, objekts)
    return objekts
