# app/dependencies/require_auth.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_session import require_session
from app.errors import ForbiddenError
from app.models.user import User
from app.models.user_key import UserKey
from app.repositories.orm import ORMRepository


async def require_auth(
    request: Request,
    session: AsyncSession = Depends(require_session),
) -> User:
    """
    Authenticate an S3 API request with AWS Signature Version 4.

    Returns the authenticated User (same contract as the previous
    JWT require_access dependency). Auth failures raise ForbiddenError
    (403). UnauthorizedError (401) stays reserved for master-password
    / gocryptfs auth (ADR-11).

    Use with signature Depends so handlers receive User. Keep
    require_gocryptfs in the route dependencies= list so the store is
    ready before this dependency opens a session (ADR-08).
    """
    repo = ORMRepository(session)

    # TODO: Parse AWS4-HMAC-SHA256 Authorization (and/or query-string
    # auth) from request. Extract access_key_id, signature, signed
    # headers, credential scope, and timestamp.
    access_key_id: str | None = None

    if not access_key_id:
        raise ForbiddenError

    key = await repo.select(UserKey, access_key_id=access_key_id)
    if key is None or not key.is_enabled:
        raise ForbiddenError

    user = await repo.select(User, id=key.user_id)
    if user is None or not user.is_enabled:
        raise ForbiddenError

    # TODO: Decrypt key.secret_access_key_encrypted and verify the
    # SigV4 signature against the canonical request built from
    # `request`. On mismatch or skew, raise ForbiddenError.

    return user
