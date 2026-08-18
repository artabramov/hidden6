# app/services/bucket_objekt_lock_update.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import S3XmlMalformedError
from app.hooks import Events, hooks
from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.objekt_lock import set_bucket_objekt_lock_configuration
from app.xml.parse_bucket_objekt_lock import parse_bucket_objekt_lock

log = logging.getLogger(__name__)


async def bucket_objekt_lock_update(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    body: bytes,
) -> None:
    """
    Apply an S3 Object Lock configuration to a bucket.

    Object Lock configuration may be applied only while bucket versioning
    is Enabled. Once enabled, Object Lock remains enabled. The optional
    default retention rule may be replaced or removed.
    """
    resource = f"/{bucket_name}"

    try:
        (
            objekt_lock_enabled,
            default_lock_mode,
            default_retention_days,
            default_retention_years,
        ) = parse_bucket_objekt_lock(body)
    except ValueError as exc:
        raise S3XmlMalformedError(resource) from exc

    repo = ORMRepository(session)
    bucket = await load_bucket(
        repo,
        bucket_name,
        current_user,
        resource,
    )

    set_bucket_objekt_lock_configuration(
        bucket=bucket,
        objekt_lock_enabled=objekt_lock_enabled,
        default_lock_mode=default_lock_mode,
        default_retention_days=default_retention_days,
        default_retention_years=default_retention_years,
        resource=resource,
    )

    try:
        await repo.update(bucket)
        await repo.commit()

    except Exception:
        try:
            await repo.rollback()
        except Exception:
            log.exception(
                "msg=rollback_failed "
                "bucket_name=%s",
                bucket_name,
            )

        raise

    await hooks.emit(Events.BUCKET_OBJECT_LOCK_UPDATED, bucket)
