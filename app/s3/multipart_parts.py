# app/s3/multipart_parts.py
# SPDX-License-Identifier: GPL-3.0-only

import os

from app.constants import (
    OBJEKT_PART_NUMBER_MAX,
    OBJEKT_PART_SIZE_MIN_BYTES,
)
from app.errors import (
    S3ObjektPartInvalidError,
    S3ObjektPartNumberInvalidError,
    S3ObjektPartOrderInvalidError,
    S3ObjektPartTooSmallError,
)
from app.repositories.io import get_filesize, isfile
from app.schemas.multipart_complete import MultipartPart


async def multipart_parts(
    upload_dir: str,
    parts: list[MultipartPart],
    resource: str,
) -> list[str]:
    """
    Map the parts listed by the client onto the files staged for the
    upload. Parts are listed in ascending order, every listed part has
    been uploaded, and every part but the last one is at least the
    minimum part size, otherwise the object cannot be assembled.
    """
    previous = 0
    paths: list[str] = []

    for part in parts:
        if part.part_number <= previous:
            raise S3ObjektPartOrderInvalidError(resource)
        if part.part_number > OBJEKT_PART_NUMBER_MAX:
            raise S3ObjektPartNumberInvalidError(resource)

        previous = part.part_number
        path = os.path.join(upload_dir, f"{part.part_number}.part")

        if not await isfile(path):
            raise S3ObjektPartInvalidError(resource)

        paths.append(path)

    for path in paths[:-1]:
        if await get_filesize(path) < OBJEKT_PART_SIZE_MIN_BYTES:
            raise S3ObjektPartTooSmallError(resource)

    return paths
