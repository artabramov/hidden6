# app/s3/objekt_upsert.py
# SPDX-License-Identifier: GPL-3.0-only

from app.models.bucket import Bucket
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.orm import ORMRepository


async def objekt_upsert(
    repo: ORMRepository,
    bucket: Bucket,
    user: User,
    object_key: str,
    size_bytes: int,
    etag: str,
    content_type: str,
) -> Objekt:
    """
    Insert the Objekt row for a new key or update the existing row when
    the key is overwritten. Changes are flushed, not committed.
    """
    objekt = await repo.select(
        Objekt,
        bucket_id=bucket.id,
        object_key=object_key,
    )

    if objekt is None:
        objekt = Objekt(
            bucket_id=bucket.id,
            user_id=user.id,
            object_key=object_key,
            size_bytes=size_bytes,
            etag=etag,
            content_type=content_type,
        )
        return await repo.insert(objekt)

    objekt.user_id = user.id
    objekt.size_bytes = size_bytes
    objekt.etag = etag
    objekt.content_type = content_type

    return await repo.update(objekt)
