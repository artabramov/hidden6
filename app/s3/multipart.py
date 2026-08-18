# app/s3/multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from app.constants import (
    OBJECT_PART_NUMBER_MAX,
    OBJECT_PART_SIZE_MIN_BYTES,
)
from app.errors import (
    S3ObjectPartInvalidError,
    S3ObjectPartNumberInvalidError,
    S3ObjectPartOrderInvalidError,
    S3ObjectPartTooSmallError,
    S3ObjectUploadNotFoundError,
)
from app.models.bucket import Bucket
from app.models.object_multipart import ObjektMultipart
from app.models.object_multipart_part import ObjektMultipartPart
from app.repositories.io import isfile
from app.repositories.orm import ORMRepository
from app.s3.paths import resolve_multipart_part_path
from app.schemas.multipart_complete import MultipartPart


async def load_multipart(
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
        raise S3ObjectUploadNotFoundError(resource)
    if multipart.bucket_id != bucket.id:
        raise S3ObjectUploadNotFoundError(resource)
    if multipart.object_key != object_key:
        raise S3ObjectUploadNotFoundError(resource)

    return multipart


async def upsert_multipart_part(
    repo: ORMRepository,
    multipart: ObjektMultipart,
    part_number: int,
    size_bytes: int,
    etag: str,
) -> ObjektMultipartPart:
    """
    Insert or update the multipart part for the specified part number.
    The staged part file must already exist when this is called.
    """
    existing = await repo.select(
        ObjektMultipartPart,
        objekt_multipart_id=multipart.id,
        part_number=part_number,
    )

    if existing is None:
        return await repo.insert(
            ObjektMultipartPart(
                objekt_multipart_id=multipart.id,
                part_number=part_number,
                size_bytes=size_bytes,
                etag=etag,
            ),
        )

    existing.size_bytes = size_bytes
    existing.etag = etag
    existing.modified_at = int(time.time())

    return await repo.update(existing)


async def list_multipart_parts(
    repo: ORMRepository,
    multipart: ObjektMultipart,
    *,
    part_number_marker: int | None = None,
    max_parts: int | None = None,
) -> list[ObjektMultipartPart]:
    """
    Return uploaded parts for a multipart upload ordered by part
    number. Optional marker and limit support a future ListParts API.
    """
    filters: dict = {
        "objekt_multipart_id": multipart.id,
        "order_by": "part_number",
        "order": "asc",
    }
    if part_number_marker is not None:
        filters["part_number__gt"] = part_number_marker
    if max_parts is not None:
        filters["limit"] = max_parts

    return await repo.select_all(ObjektMultipartPart, **filters)


async def delete_multipart_parts(
    repo: ORMRepository,
    multipart: ObjektMultipart,
) -> None:
    """
    Delete every ObjektMultipartPart row for an upload. The parts FK
    has no ON DELETE CASCADE, so callers must clear parts before the
    parent ObjektMultipart row.
    """
    rows = await list_multipart_parts(repo, multipart)
    for row in rows:
        await repo.delete(row, flush=False)
    await repo.flush()


async def load_multipart_parts(
    repo: ORMRepository,
    multipart: ObjektMultipart,
    upload_path: str,
    parts: list[MultipartPart],
    resource: str,
) -> tuple[list[str], list[str]]:
    """
    Load and validate the multipart parts listed by the client.

    Parts must be listed in ascending order, every listed part must
    have a matching ObjektMultipartPart row and staged file, and every
    part except the last must meet the minimum part size. Returns the
    staged paths and stored ETags in client order.
    """
    previous = 0
    paths: list[str] = []
    etags: list[str] = []

    for index, part in enumerate(parts):
        if part.part_number <= previous:
            raise S3ObjectPartOrderInvalidError(resource)

        if part.part_number > OBJECT_PART_NUMBER_MAX:
            raise S3ObjectPartNumberInvalidError(resource)

        previous = part.part_number

        row = await repo.select(
            ObjektMultipartPart,
            objekt_multipart_id=multipart.id,
            part_number=part.part_number,
        )
        if row is None:
            raise S3ObjectPartInvalidError(resource)

        path = resolve_multipart_part_path(
            upload_path,
            part.part_number,
        )
        if not await isfile(path):
            raise S3ObjectPartInvalidError(resource)

        if (
            index < len(parts) - 1
            and row.size_bytes < OBJECT_PART_SIZE_MIN_BYTES
        ):
            raise S3ObjectPartTooSmallError(resource)

        paths.append(path)
        etags.append(row.etag)

    return paths, etags
