# app/routers/objekt_download.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import iter_read
from app.s3.datetime import datetime_http
from app.services.objekt_download import objekt_download

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


def _objekt_headers(objekt: Objekt) -> dict[str, str]:
    last_modified = datetime_http(objekt.modified_at)
    return {
        "Content-Length": str(objekt.size_bytes),
        "ETag": f'"{objekt.etag}"',
        "Last-Modified": last_modified,
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
async def objekt_download_router(
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

    `OBJEKT_DOWNLOADED` — hook executed after the object is resolved.
    """
    objekt, object_path = await objekt_download(
        bucket_name=bucket_name,
        object_key=object_key,
        user=current_user,
        session=session,
    )
    headers = _objekt_headers(objekt)

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
