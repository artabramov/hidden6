# app/routers/multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_auth import require_auth
from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.errors import (
    S3NotImplementedError,
    S3ObjektKeyInvalidError,
    S3ObjektXmlMalformedError,
)
from app.models.user import User
from app.schemas.objekt_upload import ObjektUploadRequest
from app.services.multipart_complete import multipart_complete
from app.services.multipart_create import multipart_create
from app.xml.multipart_complete import (
    parse_complete_multipart_xml,
    render_complete_multipart_xml,
)
from app.xml.multipart_create import render_initiate_multipart_xml

# CreateMultipartUpload and CompleteMultipartUpload post the same
# object path and differ only by the uploads and uploadId query
# parameters, while routing matches the method and the path alone.
# Both therefore share this route, which dispatches to the service of
# the addressed operation.

router = APIRouter(include_in_schema=False)


@router.post(
    "/{bucket_name}/{object_key:path}",
    responses={
        400: {
            "description": (
                "The object key cannot be stored, the part list is "
                "not well formed XML, or the listed parts are "
                "unordered, unknown, or smaller than the minimum "
                "part size."
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
                "under the mountpoint, or the multipart upload is "
                "unknown because it was already completed or "
                "aborted."
            ),
        },
        501: {
            "description": (
                "The request addresses neither of the operations "
                "posted to an object, which are recognized by the "
                "uploads and uploadId query parameters."
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
    summary="Create or complete a multipart upload.",
)
async def multipart_create_router(
    bucket_name: str,
    object_key: str,
    request: Request,
    user: User = Depends(require_auth),
    session: AsyncSession = Depends(require_session),
    uploads: Annotated[str | None, Query()] = None,
    upload_id: Annotated[
        str | None,
        Query(alias="uploadId"),
    ] = None,
) -> Response:
    """
    Start or finish a multipart upload for the authenticated user.

    With `?uploads` the upload is registered for the bucket and key,
    and its upload id is returned (CreateMultipartUpload). With
    `?uploadId=` the parts listed in the request body are assembled
    into the final object (CompleteMultipartUpload).

    `OBJEKT_UPLOADED` — hook executed after the object is assembled.
    """
    resource = f"/{bucket_name}/{object_key}"

    try:
        data = ObjektUploadRequest(object_key=object_key)
    except ValidationError as exc:
        raise S3ObjektKeyInvalidError(resource) from exc

    if uploads is not None:
        multipart = await multipart_create(
            bucket_name=bucket_name,
            object_key=data.object_key,
            user=user,
            session=session,
        )
        return _xml_response(
            render_initiate_multipart_xml(
                bucket_name=bucket_name,
                object_key=data.object_key,
                upload_id=multipart.upload_id,
            ),
        )

    if upload_id is None:
        raise S3NotImplementedError(resource)

    try:
        parts = parse_complete_multipart_xml(await request.body())
    except ValueError as exc:
        raise S3ObjektXmlMalformedError(resource) from exc

    objekt = await multipart_complete(
        bucket_name=bucket_name,
        object_key=data.object_key,
        user=user,
        session=session,
        upload_id=upload_id,
        parts=parts,
    )
    return _xml_response(
        render_complete_multipart_xml(
            bucket_name=bucket_name,
            object_key=data.object_key,
            etag=objekt.etag,
        ),
    )


def _xml_response(content: str) -> Response:
    """Return an S3 XML response body with a 200 status."""
    return Response(
        content=content,
        status_code=status.HTTP_200_OK,
        media_type="application/xml",
    )
