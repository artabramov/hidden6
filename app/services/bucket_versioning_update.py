# app/services/bucket_versioning_update.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import S3XmlMalformedError
from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.versioning import set_bucket_versioning_status
from app.xml.parse_bucket_versioning import parse_bucket_versioning

log = logging.getLogger(__name__)


async def bucket_versioning_update(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    body: bytes,
) -> None:
    """
    Parse and apply an S3 bucket versioning configuration.

    Malformed XML and invalid versioning states are mapped to their
    corresponding S3 errors. The bucket state is committed atomically.
    """
    resource = f"/{bucket_name}"

    try:
        versioning_status = parse_bucket_versioning(body)
    except ValueError as exc:
        raise S3XmlMalformedError(resource) from exc

    repo = ORMRepository(session)
    bucket = await load_bucket(
        repo,
        bucket_name,
        current_user,
        resource,
    )

    set_bucket_versioning_status(
        bucket,
        versioning_status,
        resource,
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
