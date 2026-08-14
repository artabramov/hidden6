# app/services/objekt_download.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.errors import S3ObjektNotFoundError
from app.hooks import Events, hooks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import isfile
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.objekt import objekt_load
from app.s3.paths import objekt_path
from app.s3.validation import bucket_name_validate, objekt_key_validate

log = logging.getLogger(__name__)


async def objekt_download(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
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

    log.info("msg=objekt_download resource=%s", resource)

    bucket_name_validate(bucket_name, resource)
    objekt_key_validate(object_key, resource)

    _bucket_path, object_path = objekt_path(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        object_key,
    )

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)
    objekt = await objekt_load(repo, bucket, object_key, resource)

    if not await isfile(object_path):
        raise S3ObjektNotFoundError(resource)

    await hooks.emit(Events.OBJEKT_DOWNLOADED, objekt)
    return objekt, object_path
