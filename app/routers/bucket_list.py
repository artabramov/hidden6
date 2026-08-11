# app/routers/bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.models.user import User
from app.schemas.bucket_list import render_list_buckets_xml
from app.services.bucket_list import bucket_list

router = APIRouter(include_in_schema=False)


@router.get(
    "/",
    responses={
        403: {
            "description": (
                "The request could not be authenticated with AWS "
                "Signature Version 4. This includes an unknown or "
                "disabled access key, a disabled user, an invalid "
                "signature, or a request timestamp outside the "
                "allowed clock skew."
            ),
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
    summary="List S3 buckets.",
)
async def bucket_list_router(
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(require_session),
) -> Response:
    """
    Lists buckets visible to the authenticated user. Non-root users
    see only their own buckets; root lists all buckets in the store.
    Returns the bucket list in S3 XML format.

    `BUCKET_LISTED` — hook executed after the bucket list is retrieved.
    """
    buckets = await bucket_list(
        user=user,
        session=session,
    )
    return Response(
        content=render_list_buckets_xml(
            owner=user,
            buckets=buckets,
        ),
        status_code=status.HTTP_200_OK,
        media_type="application/xml",
    )
