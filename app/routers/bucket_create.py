# app/routers/bucket_create.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.errors import S3InvalidBucketNameError
from app.models.user import User
from app.schemas.bucket_create import BucketCreateRequest
from app.services.bucket_create import bucket_create

router = APIRouter(tags=["S3"])


@router.put(
    "/{bucket_name}",
    responses={
        400: {
            "description": "Invalid bucket name (InvalidBucketName).",
        },
        403: {
            "description": (
                "SigV4 failure: AccessDenied, InvalidAccessKeyId, "
                "SignatureDoesNotMatch, or RequestTimeTooSkewed."
            ),
        },
        409: {
            "description": (
                "Bucket name unavailable (BucketAlreadyExists) "
                "or already owned (BucketAlreadyOwnedByYou)."
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
    summary="Create an S3 bucket.",
)
async def bucket_create_router(
    bucket_name: str,
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(require_session),
) -> Response:
    """
    Create an S3 bucket for the authenticated user.

    Validates the bucket name, creates the bucket with the authenticated
    user as its owner, and returns the bucket location.

    `BUCKET_CREATED` — hook executed after the bucket is created.
    """
    try:
        data = BucketCreateRequest(bucket_name=bucket_name)
    except ValidationError as exc:
        raise S3InvalidBucketNameError(f"/{bucket_name}") from exc

    await bucket_create(
        bucket_name=data.bucket_name,
        user=user,
        session=session,
    )
    return Response(
        status_code=status.HTTP_200_OK,
        headers={"Location": f"/{data.bucket_name}"},
    )
