# app/routers/object_upload.py
# SPDX-License-Identifier: GPL-3.0-only

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.errors import S3ObjectPartNumberInvalidError
from app.models.user import User
from app.s3.headers import etag_headers
from app.services.multipart_upload import multipart_upload
from app.services.object_upload import objekt_upload
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
                "already stored in the bucket. A body exceeding the "
                "configured upload limit and an out-of-range part "
                "number are reported here too."
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
                "The bucket does not exist, its directory is missing "
                "under the mountpoint, or the multipart upload the "
                "part belongs to is unknown."
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
    summary="Upload an S3 object or one of its parts.",
)
async def object_upload_router(
    bucket_name: str,
    object_key: str,
    request: Request,
    session: AsyncSession = Depends(require_session),
    current_user: User = Depends(require_auth),
    upload_id: Annotated[
        str | None,
        Query(alias="uploadId"),
    ] = None,
    part_number: Annotated[
        int | None,
        Query(alias="partNumber"),
    ] = None,
) -> Response:
    """
    Upload an object into a bucket for the authenticated user.

    Validates the object key, streams the request body into the bucket
    owned by the caller (or into any bucket for root), and returns the
    ETag of the stored bytes. When the request carries an upload id,
    the body is stored as a single part of that multipart upload
    (UploadPart) instead of becoming an object of its own (PutObject).

    `OBJECT_UPLOADED` — hook executed after the object is uploaded.
    """
    resource = f"/{bucket_name}/{object_key}"

    config = get_config()
    body = build_body_reader(
        request,
        max_bytes=config.S3_UPLOAD_MAX_BYTES,
        resource=resource,
    )

    if upload_id is not None:
        if part_number is None:
            raise S3ObjectPartNumberInvalidError(resource)

        etag = await multipart_upload(
            session=session,
            current_user=current_user,
            bucket_name=bucket_name,
            object_key=object_key,
            upload_id=upload_id,
            part_number=part_number,
            body=body,
        )
        return Response(
            status_code=status.HTTP_200_OK,
            headers=etag_headers(etag),
        )

    objekt = await objekt_upload(
        session=session,
        current_user=current_user,
        bucket_name=bucket_name,
        object_key=object_key,
        body=body,
    )
    return Response(
        status_code=status.HTTP_200_OK,
        headers=etag_headers(objekt.etag),
    )
