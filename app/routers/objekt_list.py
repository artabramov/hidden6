# app/routers/objekt_list.py
# SPDX-License-Identifier: GPL-3.0-only

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.models.user import User
from app.services.objekt_list import objekt_list
from app.xml.render_objekt_list import render_objekt_list

router = APIRouter(include_in_schema=False)

_MAX_KEYS_LIMIT = 1000
_MAX_KEYS_DEFAULT = 1000


@router.get(
    "/{bucket_name}",
    responses={
        400: {
            "description": (
                "The bucket name in the path does not satisfy S3 "
                "DNS naming rules."
            ),
        },
        403: {
            "description": (
                "The request could not be authenticated with AWS "
                "Signature Version 4, or the bucket belongs to "
                "another user and the caller is not root."
            ),
        },
        404: {
            "description": "The bucket does not exist.",
        },
        503: {
            "description": (
                "Gocryptfs infrastructure is not ready: cipherdir "
                "is not initialized, not mounted, or the required "
                "passphrase is missing."
            ),
        },
    },
    status_code=status.HTTP_200_OK,
    response_class=Response,
    dependencies=[Depends(require_gocryptfs())],
    summary="List objects in an S3 bucket.",
)
async def objekt_list_router(
    bucket_name: str,
    session: AsyncSession = Depends(require_session),
    current_user: User = Depends(require_auth),
    prefix: Annotated[str, Query()] = "",
    max_keys: Annotated[
        int,
        Query(alias="max-keys", ge=0, le=_MAX_KEYS_LIMIT),
    ] = _MAX_KEYS_DEFAULT,
) -> Response:
    """
    List objects in the specified bucket for the authenticated user.

    Returns up to max-keys objects whose key starts with the given
    prefix, ordered lexicographically by key, in S3 XML format.

    `OBJEKT_LISTED` — hook executed after the object list is retrieved.
    """
    objekts = await objekt_list(
        bucket_name=bucket_name,
        user=current_user,
        session=session,
        prefix=prefix,
        max_keys=max_keys,
    )
    return Response(
        content=render_objekt_list(
            bucket_name=bucket_name,
            prefix=prefix,
            max_keys=max_keys,
            objekts=objekts,
        ),
        status_code=status.HTTP_200_OK,
        media_type="application/xml",
    )
