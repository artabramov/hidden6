# app/routers/object_download.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.models.user import User
from app.repositories.io import iter_read
from app.s3.headers import object_headers
from app.services.object_download import object_download

router = APIRouter(include_in_schema=False)

_RESPONSES = {
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
            "The bucket does not exist, or the object key is "
            "missing from the store or from the mountpoint."
        ),
    },
    503: {
        "description": (
            "Gocryptfs infrastructure is not ready: cipherdir "
            "is not initialized, not mounted, or the required "
            "passphrase is missing."
        ),
    },
}


@router.api_route(
    "/{bucket_name}/{object_key:path}",
    methods=["GET", "HEAD"],
    responses=_RESPONSES,
    status_code=status.HTTP_200_OK,
    response_class=Response,
    dependencies=[Depends(require_gocryptfs())],
    summary="Download an S3 object or fetch its metadata.",
)
async def object_download_router(
    bucket_name: str,
    object_key: str,
    request: Request,
    session: AsyncSession = Depends(require_session),
    current_user: User = Depends(require_auth),
) -> Response:
    """
    Download an object (GetObject) or return only its metadata
    (HeadObject) for the authenticated user.

    GetObject streams the object bytes. HeadObject returns the same
    Content-Type, Content-Length, ETag, and Last-Modified headers
    without a body — AWS CLI issues HeadObject before every copy.

    `OBJECT_DOWNLOADED` — hook executed after the object is resolved.
    """
    objekt, object_path = await object_download(
        session=session,
        current_user=current_user,
        bucket_name=bucket_name,
        object_key=object_key,
    )
    headers = object_headers(objekt)

    if request.method == "HEAD":
        return Response(
            status_code=status.HTTP_200_OK,
            media_type=objekt.content_type,
            headers=headers,
        )

    return StreamingResponse(
        iter_read(object_path),
        status_code=status.HTTP_200_OK,
        media_type=objekt.content_type,
        headers=headers,
    )
