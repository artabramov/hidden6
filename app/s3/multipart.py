# app/s3/multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from app.constants import (
    OBJEKT_PART_NUMBER_MAX,
    OBJEKT_PART_SIZE_MIN_BYTES,
)
from app.errors import (
    S3ObjektPartInvalidError,
    S3ObjektPartNumberInvalidError,
    S3ObjektPartOrderInvalidError,
    S3ObjektPartTooSmallError,
    S3ObjektUploadNotFoundError,
)
from app.models.bucket import Bucket
from app.models.objekt_multipart import ObjektMultipart
from app.models.objekt_multipart_part import ObjektMultipartPart
from app.repositories.io import isfile
from app.repositories.orm import ORMRepository
from app.s3.paths import resolve_multipart_part_path
from app.schemas.multipart_complete import MultipartPart


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


async def multipart_part_upsert(
    repo: ORMRepository,
    multipart: ObjektMultipart,
    part_number: int,
    size_bytes: int,
    etag: str,
) -> ObjektMultipartPart:
    """
    Insert or replace the ObjektMultipartPart row for one part number.
    The staged part file must already exist when this is called.
    """
    existing = await repo.select(
        ObjektMultipartPart,
        objekt_multipart_id=multipart.id,
        part_number=part_number,
    )
    modified_at = int(time.time())

    if existing is None:
        return await repo.insert(
            ObjektMultipartPart(
                objekt_multipart_id=multipart.id,
                part_number=part_number,
                size_bytes=size_bytes,
                etag=etag,
                modified_at=modified_at,
            ),
        )

    existing.size_bytes = size_bytes
    existing.etag = etag
    existing.modified_at = modified_at
    return await repo.update(existing)


async def multipart_parts_list(
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


async def multipart_parts_delete(
    repo: ORMRepository,
    multipart: ObjektMultipart,
) -> None:
    """
    Delete every ObjektMultipartPart row for an upload. The parts FK
    has no ON DELETE CASCADE, so callers must clear parts before the
    parent ObjektMultipart row.
    """
    rows = await multipart_parts_list(repo, multipart)
    for row in rows:
        await repo.delete(row, flush=False)
    await repo.flush()


async def multipart_parts(
    repo: ORMRepository,
    multipart: ObjektMultipart,
    upload_dir: str,
    parts: list[MultipartPart],
    resource: str,
) -> tuple[list[str], list[str]]:
    """
    Resolve the parts listed by the client against ObjektMultipartPart
    rows and staged files. Parts must be listed in ascending order,
    every listed part must have been uploaded, and every part but the
    last must be at least the minimum part size. Returns the staged
    paths and stored ETags in client order.
    """
    previous = 0
    paths: list[str] = []
    etags: list[str] = []
    sizes: list[int] = []

    for part in parts:
        if part.part_number <= previous:
            raise S3ObjektPartOrderInvalidError(resource)
        if part.part_number > OBJEKT_PART_NUMBER_MAX:
            raise S3ObjektPartNumberInvalidError(resource)

        previous = part.part_number

        row = await repo.select(
            ObjektMultipartPart,
            objekt_multipart_id=multipart.id,
            part_number=part.part_number,
        )
        if row is None:
            raise S3ObjektPartInvalidError(resource)

        path = resolve_multipart_part_path(upload_dir, part.part_number)
        if not await isfile(path):
            raise S3ObjektPartInvalidError(resource)

        paths.append(path)
        etags.append(row.etag)
        sizes.append(row.size_bytes)

    for size_bytes in sizes[:-1]:
        if size_bytes < OBJEKT_PART_SIZE_MIN_BYTES:
            raise S3ObjektPartTooSmallError(resource)

    return paths, etags
