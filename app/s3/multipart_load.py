# app/s3/multipart_load.py
# SPDX-License-Identifier: GPL-3.0-only

from app.errors import S3ObjektUploadNotFoundError
from app.models.bucket import Bucket
from app.models.objekt_multipart import ObjektMultipart
from app.repositories.orm import ORMRepository


async def multipart_load(
    repo: ORMRepository,
    bucket: Bucket,
    object_key: str,
    upload_id: str,
    resource: str,
) -> ObjektMultipart:
    """
    Load an in-progress upload and check that it belongs to the bucket
    and key being addressed. The caller has been authorized against the
    bucket, so its owner and root may upload parts into, finish, or
    abort any upload started in it.
    """
    multipart = await repo.select(ObjektMultipart, upload_id=upload_id)

    if multipart is None:
        raise S3ObjektUploadNotFoundError(resource)
    if multipart.bucket_id != bucket.id:
        raise S3ObjektUploadNotFoundError(resource)
    if multipart.object_key != object_key:
        raise S3ObjektUploadNotFoundError(resource)

    return multipart
