# app/services/multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import (
    OBJEKT_CONTENT_TYPE_DEFAULT,
    OBJEKT_PART_NUMBER_MAX,
    OBJEKT_PART_SIZE_MIN_BYTES,
)
from app.errors import (
    S3ObjektPartInvalidError,
    S3ObjektPartNumberInvalidError,
    S3ObjektPartOrderInvalidError,
    S3ObjektPartTooSmallError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.file import (
    concat,
    delete,
    get_filesize,
    get_mimetype,
    isfile,
    rename,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket_assert import bucket_assert
from app.s3.bucket_load import bucket_load
from app.s3.multipart_cleanup import multipart_cleanup
from app.s3.multipart_load import multipart_load
from app.s3.objekt_mkdir import objekt_mkdir
from app.s3.objekt_path import objekt_path
from app.s3.objekt_upsert import objekt_upsert
from app.schemas.multipart_complete import MultipartPart

log = logging.getLogger(__name__)


async def multipart_complete(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    upload_id: str,
    parts: list[MultipartPart],
) -> Objekt:
    """
    Assemble the uploaded parts into a single object (S3
    CompleteMultipartUpload): concatenate the parts listed by the
    client, publish the result under the bucket directory, upsert the
    Objekt row, and drop the upload with its staged parts.
    """
    log.info(
        "msg=multipart_complete_started upload_id=%s parts=%d",
        upload_id,
        len(parts),
    )

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)
    multipart = await multipart_load(
        repo=repo,
        bucket_name=bucket_name,
        object_key=object_key,
        user=user,
        upload_id=upload_id,
        resource=resource,
        bucket=bucket,
    )

    upload_dir = os.path.join(config.MOUNTPOINT_TMP_DIR, upload_id)
    part_paths = await _resolve_part_paths(
        upload_dir,
        parts,
        resource,
    )

    bucket_path = os.path.join(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
    )
    object_path = objekt_path(bucket_path, object_key, resource)
    staged_path = os.path.join(
        config.MOUNTPOINT_TMP_DIR,
        uuid.uuid4().hex,
    )

    try:
        part_hashes = await concat(part_paths, staged_path)
        _assert_part_hashes(parts, part_hashes, resource)

        size_bytes = await get_filesize(staged_path)
        content_type = await get_mimetype(staged_path)

        async with locks.lock_directory(bucket_path, LockType.WRITE):
            await bucket_assert(bucket_path, resource)
            await objekt_mkdir(object_path, resource)

            objekt = await objekt_upsert(
                repo=repo,
                bucket=bucket,
                user=user,
                object_key=object_key,
                size_bytes=size_bytes,
                etag=_multipart_etag(part_hashes),
                content_type=content_type or OBJEKT_CONTENT_TYPE_DEFAULT,
            )
            await repo.delete(multipart)
            await rename(staged_path, object_path)
            await repo.commit()

    except Exception:
        await repo.rollback()
        await delete(staged_path)
        raise

    await multipart_cleanup(upload_dir)

    log.info(
        "msg=multipart_completed bucket=%s key=%s size=%d",
        bucket_name,
        object_key,
        size_bytes,
    )
    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)

    return objekt


async def _resolve_part_paths(
    upload_dir: str,
    parts: list[MultipartPart],
    resource: str,
) -> list[str]:
    """
    Map the listed parts onto staged part files, checking that they
    are ordered, present, and large enough to be concatenated.
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


def _assert_part_hashes(
    parts: list[MultipartPart],
    part_hashes: list[str],
    resource: str,
) -> None:
    """
    Compare the ETag the client listed for every part with the hash of
    the bytes actually stored for it.
    """
    for part, part_hash in zip(parts, part_hashes):
        if part.etag != part_hash:
            raise S3ObjektPartInvalidError(resource)


def _multipart_etag(part_hashes: list[str]) -> str:
    """
    Build the ETag of an assembled object: the MD5 of the concatenated
    part digests, suffixed with the number of parts.
    """
    digests = b"".join(bytes.fromhex(value) for value in part_hashes)
    digest = hashlib.md5(digests, usedforsecurity=False).hexdigest()

    return f"{digest}-{len(part_hashes)}"
