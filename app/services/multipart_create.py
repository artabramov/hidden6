# app/services/multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJECT_CONTENT_TYPE_DEFAULT
from app.models.object_multipart import ObjektMultipart
from app.models.user import User
from app.repositories.io import mktree, rmtree
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.paths import resolve_multipart_path
from app.s3.validation import validate_objekt_key

log = logging.getLogger(__name__)


async def multipart_create(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    objekt_key: str,
    content_type: str | None = None,
) -> ObjektMultipart:
    """
    Create an S3 multipart upload. The operation is transactional at
    the DB level and reconciles filesystem state on failure. A dedicated
    temporary directory is created to hold uploaded parts until the
    multipart upload is completed or aborted.

    (1) generate a multipart upload ID
    (2) create the multipart upload directory
    (3) create the multipart upload record
    (4) commit

    On failure of the transaction, the session is rolled back and the
    temporary upload directory is removed as a best-effort cleanup step.
    """
    config = get_config()
    resource = f"/{bucket_name}/{objekt_key}"

    validate_objekt_key(objekt_key, resource)

    repo = ORMRepository(session)
    bucket = await load_bucket(repo, bucket_name, current_user, resource)

    upload_id = uuid.uuid4().hex

    # Path used to store parts for the new multipart
    # upload until it is completed or aborted.
    upload_path = resolve_multipart_path(
        config.MOUNTPOINT_TMP_DIR,
        upload_id,
    )

    multipart = ObjektMultipart(
        bucket_id=bucket.id,
        user_id=current_user.id,
        upload_id=upload_id,
        object_key=objekt_key,
        content_type=content_type or OBJECT_CONTENT_TYPE_DEFAULT,
    )

    try:
        await mktree(upload_path)
        await repo.insert(multipart)
        await repo.commit()

    except Exception:
        try:
            await repo.rollback()
        except Exception:
            log.exception(
                "msg=rollback_failed "
                "bucket_name=%s "
                "object_key=%s "
                "upload_id=%s",
                bucket_name,
                objekt_key,
                upload_id,
            )

        try:
            await rmtree(upload_path)
        except Exception:
            log.exception(
                "msg=cleanup_failed "
                "upload_path=%s",
                upload_path,
            )

        raise

    return multipart
