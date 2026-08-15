# app/routers/multipart_abort.py
# SPDX-License-Identifier: GPL-3.0-only

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.errors import S3NotImplementedError
from app.models.user import User
from app.services.multipart_abort import multipart_abort

router = APIRouter(include_in_schema=False)


@router.delete(
    "/{bucket_name}/{object_key:path}",
    responses={
        400: {
            "description": (
                "The object key cannot be stored: it is empty, "
                "longer than 1024 bytes, or contains segments that "
                "do not map onto a path."
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
            "description": (
                "The bucket does not exist, or the multipart upload "
                "is unknown because it was already completed or "
                "aborted."
            ),
        },
        501: {
            "description": (
                "The request deletes a stored object, which this "
                "server does not implement yet."
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
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_gocryptfs())],
    summary="Abort a multipart upload.",
)
async def multipart_abort_router(
    bucket_name: str,
    object_key: str,
    session: AsyncSession = Depends(require_session),
    current_user: User = Depends(require_auth),
    upload_id: Annotated[
        str | None,
        Query(alias="uploadId"),
    ] = None,
) -> Response:
    """
    Abort the multipart upload identified by `?uploadId=`, discarding
    every part staged for it. Deleting a stored object is a different
    operation and is not implemented yet.
    """
    resource = f"/{bucket_name}/{object_key}"

    if upload_id is None:
        raise S3NotImplementedError(resource)

    await multipart_abort(
        bucket_name=bucket_name,
        object_key=object_key,
        user=current_user,
        session=session,
        upload_id=upload_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
