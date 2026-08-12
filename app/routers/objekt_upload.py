# app/routers/objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.errors import S3ObjektKeyInvalidError
from app.models.user import User
from app.schemas.objekt_upload import ObjektUploadRequest
from app.services.objekt_upload import objekt_upload
from app.streams import build_body_reader

router = APIRouter(include_in_schema=False)


@router.put(
    "/{bucket_name}/{object_key:path}",
    responses={
        400: {
            "description": (
                "The object key cannot be stored: it is empty, "
                "longer than 1024 bytes, contains segments that do "
                "not map onto a path, or collides with an object "
                "already stored in the bucket. The body exceeding "
                "the configured upload limit is reported here too."
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
                "The bucket does not exist, or its directory is "
                "missing under the mountpoint."
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
    summary="Upload an S3 object.",
)
async def objekt_upload_router(
    bucket_name: str,
    object_key: str,
    request: Request,
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(require_session),
) -> Response:
    """
    Upload an object into a bucket for the authenticated user.

    Validates the object key, streams the request body into the bucket
    owned by the caller (or into any bucket for root), stores the
    object metadata, and returns the ETag of the stored bytes.

    `OBJEKT_UPLOADED` — hook executed after the object is uploaded.
    """
    resource = f"/{bucket_name}/{object_key}"

    try:
        data = ObjektUploadRequest(object_key=object_key)
    except ValidationError as exc:
        raise S3ObjektKeyInvalidError(resource) from exc

    config = get_config()
    body = build_body_reader(
        request,
        max_bytes=config.S3_UPLOAD_MAX_BYTES,
        resource=resource,
    )

    objekt = await objekt_upload(
        bucket_name=bucket_name,
        object_key=data.object_key,
        user=user,
        session=session,
        body=body,
    )
    return Response(
        status_code=status.HTTP_200_OK,
        headers={"ETag": f'"{objekt.etag}"'},
    )
