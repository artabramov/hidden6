# app/services/multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT
from app.models.objekt_multipart import ObjektMultipart
from app.models.user import User
from app.repositories.io import mktree, rmtree
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.objekt import objekt_key_validate

log = logging.getLogger(__name__)


async def multipart_create(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    content_type: str | None = None,
) -> ObjektMultipart:
    """
    Start a multipart upload (S3 CreateMultipartUpload): register the
    upload for the bucket and key, store the Content-Type that will be
    assigned to the assembled object, and prepare the directory holding
    its parts until the upload is completed or aborted.
    """
    log.info("msg=multipart_create bucket=%s key=%s", bucket_name, object_key)

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    objekt_key_validate(object_key, resource)

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)

    upload_id = uuid.uuid4().hex
    upload_dir = os.path.join(config.MOUNTPOINT_TMP_DIR, upload_id)
    await mktree(upload_dir)

    multipart = ObjektMultipart(
        bucket_id=bucket.id,
        user_id=user.id,
        upload_id=upload_id,
        object_key=object_key,
        content_type=content_type or OBJEKT_CONTENT_TYPE_DEFAULT,
    )
    try:
        await repo.insert(multipart, commit=True)
    except Exception:
        await repo.rollback()
        await rmtree(upload_dir)
        raise

    log.info("msg=multipart_created bucket=%s key=%s upload_id=%s", bucket_name, object_key, upload_id)  # noqa: E501
    return multipart
