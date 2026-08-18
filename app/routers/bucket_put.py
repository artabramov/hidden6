# app/routers/bucket_put.py
# SPDX-License-Identifier: GPL-3.0-only

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.models.user import User
from app.services.bucket_create import bucket_create
from app.services.bucket_versioning_update import bucket_versioning_update
from app.services.bucket_object_lock_update import bucket_object_lock_update

router = APIRouter(include_in_schema=False)


@router.put(
    "/{bucket_name}",
    responses={
        400: {
            "description": (
                "The bucket name or bucket configuration is invalid, "
                "or the request XML is malformed."
            ),
        },
        403: {
            "description": (
                "The request could not be authenticated with AWS "
                "Signature Version 4. This includes an unknown or "
                "disabled access key, a disabled user, an invalid "
                "signature, or a request timestamp outside the "
                "allowed clock skew."
            ),
        },
        409: {
            "description": (
                "The bucket name is unavailable, or the requested "
                "bucket configuration is incompatible with the current "
                "bucket state."
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
    summary="Create a bucket or update bucket configuration.",
)
async def bucket_put_router(
    bucket_name: str,
    request: Request,
    session: AsyncSession = Depends(require_session),
    current_user: User = Depends(require_auth),
    versioning: Annotated[str | None, Query()] = None,
    objekt_lock: Annotated[str | None, Query(alias="object-lock")] = None,
) -> Response:
    """
    Handle S3 PUT operations addressed to a bucket.

    With `?object-lock`, apply the Object Lock configuration from the
    request body. With `?versioning`, apply the versioning configuration.
    Otherwise create the bucket for the authenticated user.

    `BUCKET_CREATED` — hook executed after the bucket is created.
    """
    if objekt_lock is not None:
        await bucket_object_lock_update(
            session=session,
            current_user=current_user,
            bucket_name=bucket_name,
            body=await request.body(),
        )

        return Response(
            status_code=status.HTTP_200_OK,
        )

    if versioning is not None:
        await bucket_versioning_update(
            session=session,
            current_user=current_user,
            bucket_name=bucket_name,
            body=await request.body(),
        )

        return Response(status_code=status.HTTP_200_OK)

    await bucket_create(
        session=session,
        current_user=current_user,
        bucket_name=bucket_name,
    )

    return Response(
        status_code=status.HTTP_200_OK,
        headers={"Location": f"/{bucket_name}"},
    )
