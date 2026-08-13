# app/s3/objekt_load.py
# SPDX-License-Identifier: GPL-3.0-only

from app.errors import S3ObjektNotFoundError
from app.models.bucket import Bucket
from app.models.objekt import Objekt
from app.repositories.orm import ORMRepository


async def objekt_load(
    repo: ORMRepository,
    bucket: Bucket,
    object_key: str,
    resource: str,
) -> Objekt:
    """
    Load the Objekt row for a key inside a bucket. A missing row is
    reported as NoSuchKey — the same code S3 uses when the object
    is absent from the store.
    """
    objekt = await repo.select(
        Objekt,
        bucket_id=bucket.id,
        object_key=object_key,
    )

    if objekt is None:
        raise S3ObjektNotFoundError(resource)

    return objekt
