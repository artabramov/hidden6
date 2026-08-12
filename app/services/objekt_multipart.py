# app/services/objekt_multipart.py
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
    S3ObjektUploadNotFoundError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.objekt_multipart import ObjektMultipart
from app.models.user import User
from app.repositories.file import (
    AsyncReadable,
    concat,
    delete,
    get_file_hash,
    get_filesize,
    get_mimetype,
    isdir,
    isfile,
    listdir,
    mkdir,
    rename,
    rmdir,
    upload,
)
from app.repositories.orm import ORMRepository
from app.schemas.objekt_multipart import MultipartPart
from app.services.objekt_store import (
    assert_bucket_dir,
    load_bucket,
    mkdir_object_parent,
    resolve_object_path,
    upsert_objekt,
)

log = logging.getLogger(__name__)


# TODO: Expire abandoned multipart uploads, dropping the row and the
# staged parts of an upload that is never completed or aborted.

async def multipart_create(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
) -> ObjektMultipart:
    """
    Start a multipart upload (S3 CreateMultipartUpload): register the
    upload for the bucket and key, and prepare the directory holding
    its parts until the upload is completed or aborted.
    """
    log.info(
        "msg=multipart_create_started bucket=%s key=%s",
        bucket_name,
        object_key,
    )

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    repo = ORMRepository(session)
    bucket = await load_bucket(repo, bucket_name, user, resource)

    upload_id = uuid.uuid4().hex
    upload_dir = _upload_dir(config.MOUNTPOINT_TMP_DIR, upload_id)
    await mkdir(upload_dir)

    multipart = ObjektMultipart(
        bucket_id=bucket.id,
        user_id=user.id,
        upload_id=upload_id,
        object_key=object_key,
    )
    try:
        await repo.insert(multipart, commit=True)
    except Exception:
        await repo.rollback()
        await _remove_upload_dir(upload_dir)
        raise

    log.info(
        "msg=multipart_created bucket=%s key=%s upload_id=%s",
        bucket_name,
        object_key,
        upload_id,
    )

    return multipart


async def multipart_upload(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    upload_id: str,
    part_number: int,
    body: AsyncReadable,
) -> str:
    """
    Store one part of a multipart upload (S3 UploadPart) and return
    its ETag. Uploading the same part number again replaces the part
    that was stored before.
    """
    log.info(
        "msg=multipart_upload_started upload_id=%s part=%d",
        upload_id,
        part_number,
    )

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"

    if part_number < 1 or part_number > OBJEKT_PART_NUMBER_MAX:
        raise S3ObjektPartNumberInvalidError(resource)

    repo = ORMRepository(session)
    await _load_multipart(
        repo=repo,
        bucket_name=bucket_name,
        object_key=object_key,
        user=user,
        upload_id=upload_id,
        resource=resource,
    )

    upload_dir = _upload_dir(config.MOUNTPOINT_TMP_DIR, upload_id)
    part_path = _part_path(upload_dir, part_number)

    if not await isdir(upload_dir):
        raise S3ObjektUploadNotFoundError(resource)

    # A failed upload leaves the part that was stored before in place,
    # because the body is staged and only then replaces the part file.
    async with locks.lock_file(part_path, LockType.WRITE):
        await upload(body, part_path)
        etag = await get_file_hash(part_path)

    log.info(
        "msg=multipart_uploaded upload_id=%s part=%d",
        upload_id,
        part_number,
    )

    return etag


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
    bucket = await load_bucket(repo, bucket_name, user, resource)
    multipart = await _load_multipart(
        repo=repo,
        bucket_name=bucket_name,
        object_key=object_key,
        user=user,
        upload_id=upload_id,
        resource=resource,
        bucket=bucket,
    )

    upload_dir = _upload_dir(config.MOUNTPOINT_TMP_DIR, upload_id)
    part_paths = await _resolve_part_paths(upload_dir, parts, resource)

    bucket_path = os.path.join(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
    )
    object_path = resolve_object_path(bucket_path, object_key, resource)
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
            await assert_bucket_dir(bucket_path, resource)
            await mkdir_object_parent(object_path, resource)

            objekt = await upsert_objekt(
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

    await _remove_upload_dir(upload_dir)

    log.info(
        "msg=multipart_completed bucket=%s key=%s size=%d",
        bucket_name,
        object_key,
        size_bytes,
    )
    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)

    return objekt


async def multipart_abort(
    bucket_name: str,
    object_key: str,
    user: User,
    session: AsyncSession,
    upload_id: str,
) -> None:
    """
    Abort a multipart upload (S3 AbortMultipartUpload): drop the
    upload together with every part staged for it.
    """
    log.info("msg=multipart_abort_started upload_id=%s", upload_id)

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    repo = ORMRepository(session)
    multipart = await _load_multipart(
        repo=repo,
        bucket_name=bucket_name,
        object_key=object_key,
        user=user,
        upload_id=upload_id,
        resource=resource,
    )

    await repo.delete(multipart, commit=True)
    await _remove_upload_dir(
        _upload_dir(config.MOUNTPOINT_TMP_DIR, upload_id),
    )

    log.info("msg=multipart_aborted upload_id=%s", upload_id)


async def _load_multipart(
    repo: ORMRepository,
    bucket_name: str,
    object_key: str,
    user: User,
    upload_id: str,
    resource: str,
    bucket=None,
) -> ObjektMultipart:
    """
    Load an in-progress upload and check that it belongs to the bucket
    and key being addressed. The caller is authorized against the
    bucket, so the bucket owner and root may finish or abort any
    upload started in it.
    """
    if bucket is None:
        bucket = await load_bucket(repo, bucket_name, user, resource)

    multipart = await repo.select(ObjektMultipart, upload_id=upload_id)

    if multipart is None:
        raise S3ObjektUploadNotFoundError(resource)
    if multipart.bucket_id != bucket.id:
        raise S3ObjektUploadNotFoundError(resource)
    if multipart.object_key != object_key:
        raise S3ObjektUploadNotFoundError(resource)

    return multipart


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
        path = _part_path(upload_dir, part.part_number)

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


def _upload_dir(tmp_dir: str, upload_id: str) -> str:
    """
    Return the directory holding the parts of an upload. Uploads are
    staged in the tmp dir next to the bodies of single uploads, each
    one under the upload id issued to the client.
    """
    return os.path.join(tmp_dir, upload_id)


def _part_path(upload_dir: str, part_number: int) -> str:
    """Return the path of a single staged part."""
    return os.path.join(upload_dir, f"part.{part_number:05d}")


async def _remove_upload_dir(upload_dir: str) -> None:
    """
    Delete the staged parts of an upload and their directory. Cleanup
    runs after the upload has already been completed or aborted, so a
    failure is logged instead of failing the operation.
    """
    try:
        if not await isdir(upload_dir):
            return

        for name in await listdir(upload_dir):
            await delete(os.path.join(upload_dir, name))

        await rmdir(upload_dir)

    except OSError:
        log.exception(
            "msg=multipart_cleanup_failed path=%s",
            upload_dir,
        )
