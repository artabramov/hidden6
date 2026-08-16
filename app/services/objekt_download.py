# app/services/objekt_download.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.errors import S3ObjektNotFoundError
from app.hooks import Events, hooks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import isfile
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.objekt import load_objekt
from app.s3.paths import resolve_objekt_path
from app.s3.validation import validate_bucket_name, validate_objekt_key


async def objekt_download(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    objekt_key: str,
) -> tuple[Objekt, str]:
    """
    Resolve an S3 object for download.

    Validates the key, authorizes the caller against the bucket,
    loads object metadata, and confirms the bytes are present on
    disk. Returns the metadata row and the filesystem path the
    router streams to the client.
    """
    config = get_config()
    resource = f"/{bucket_name}/{objekt_key}"

    validate_bucket_name(bucket_name, resource)
    validate_objekt_key(objekt_key, resource)

    _bucket_path, object_path = resolve_objekt_path(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        objekt_key,
    )

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, current_user, resource)
    objekt = await load_objekt(repo, bucket, objekt_key, resource)

    if not await isfile(object_path):
        raise S3ObjektNotFoundError(resource)

    await hooks.emit(Events.OBJEKT_DOWNLOADED, objekt)
    return objekt, object_path
