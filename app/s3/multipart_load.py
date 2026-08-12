# app/s3/multipart_load.py
# SPDX-License-Identifier: GPL-3.0-only

from app.errors import S3ObjektUploadNotFoundError
from app.models.bucket import Bucket
from app.models.objekt_multipart import ObjektMultipart
from app.models.user import User
from app.repositories.orm import ORMRepository
from app.s3.bucket_load import bucket_load


async def multipart_load(
    repo: ORMRepository,
    bucket_name: str,
    object_key: str,
    user: User,
    upload_id: str,
    resource: str,
    bucket: Bucket | None = None,
) -> ObjektMultipart:
    """
    Load an in-progress upload and check that it belongs to the bucket
    and key being addressed. The caller is authorized against the
    bucket, so the bucket owner and root may upload parts into, finish,
    or abort any upload started in it.
    """
    if bucket is None:
        bucket = await bucket_load(repo, bucket_name, user, resource)

    multipart = await repo.select(ObjektMultipart, upload_id=upload_id)

    if multipart is None:
        raise S3ObjektUploadNotFoundError(resource)
    if multipart.bucket_id != bucket.id:
        raise S3ObjektUploadNotFoundError(resource)
    if multipart.object_key != object_key:
        raise S3ObjektUploadNotFoundError(resource)

    return multipart
