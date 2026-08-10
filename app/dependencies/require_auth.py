# app/dependencies/require_auth.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.dependencies.require_session import require_session
from app.errors import ForbiddenError
from app.models.user import User
from app.models.user_key import UserKey
from app.repositories.orm import ORMRepository
from app.security.encryption import decrypt_string
from app.security.sigv4 import (
    extract_sigv4_auth,
    resolve_payload_hash,
    verify_sigv4,
)


async def require_auth(
    request: Request,
    session: AsyncSession = Depends(require_session),
) -> User:
    """
    Authenticate an S3 request using AWS Signature Version 4.

    Validates the access key, user state, and request signature,
    then returns the authenticated User. Authentication failures
    raise ForbiddenError (401).
    """
    config = get_config()
    auth = extract_sigv4_auth(request)
    payload_hash = await resolve_payload_hash(request)

    repo = ORMRepository(session)

    key = await repo.select(UserKey, access_key_id=auth.access_key_id)
    if key is None or not key.is_enabled:
        raise ForbiddenError

    user = await repo.select(User, id=key.user_id)
    if user is None or not user.is_enabled:
        raise ForbiddenError

    secret_access_key = decrypt_string(key.secret_access_key_encrypted)
    verify_sigv4(
        request,
        auth,
        secret_access_key,
        expected_region=config.S3_REGION,
        expected_service=config.S3_SERVICE,
        max_skew_seconds=config.S3_SIGV4_MAX_SKEW_SECONDS,
        payload_hash=payload_hash,
    )

    return user
