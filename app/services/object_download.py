# app/services/object_download.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.errors import S3ObjectNotFoundError
from app.hooks import Events, hooks
from app.models.object import Objekt
from app.models.user import User
from app.repositories.io import isfile
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.object import load_object
from app.s3.paths import resolve_object_path
from app.s3.validation import validate_bucket_name, validate_object_key


async def object_download(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    object_key: str,
) -> tuple[Objekt, str]:
    """
    Resolve an S3 object for download.

    Validates the key, authorizes the caller against the bucket,
    loads object metadata, and confirms the bytes are present on
    disk. Returns the metadata row and the filesystem path the
    router streams to the client.
    """
    config = get_config()
    resource = f"/{bucket_name}/{object_key}"

    validate_bucket_name(bucket_name, resource)
    validate_object_key(object_key, resource)

    _bucket_path, object_path = resolve_object_path(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        object_key,
    )

    repo = ORMRepository(session)
    bucket = await load_bucket(repo, bucket_name, current_user, resource)
    objekt = await load_object(repo, bucket, object_key, resource)

    if not await isfile(object_path):
        raise S3ObjectNotFoundError(resource)

    await hooks.emit(Events.OBJECT_DOWNLOADED, objekt)
    return objekt, object_path
