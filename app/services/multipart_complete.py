# app/services/multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.errors import S3BucketNotFoundError, S3ObjektPartInvalidError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import (
    concat,
    delete,
    get_filesize,
    isdir,
    isfile,
    rename,
    rmtree,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.etag import etag_construct
from app.s3.multipart import (
    multipart_load,
    multipart_parts,
    multipart_parts_delete,
)
from app.s3.objekt import objekt_mkdir, objekt_upsert
from app.s3.paths import multipart_path, objekt_path
from app.s3.validation import bucket_name_validate, objekt_key_validate
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
    CompleteMultipartUpload). The multipart directory WRITE lock is
    held until the upload row is committed away so UploadPart cannot
    interleave after validation. When an existing object is overwritten,
    its bytes stay on a same-directory backup until commit succeeds.
    """
    log.info("msg=multipart_complete upload_id=%s parts=%d", upload_id, len(parts))  # noqa: E501

    config = get_config()
    resource = f"/{bucket_name}/{object_key}"
    bucket_name_validate(bucket_name, resource)
    objekt_key_validate(object_key, resource)

    bucket_path, object_path = objekt_path(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        object_key,
    )

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, user, resource)

    multipart = await multipart_load(
        repo=repo,
        bucket=bucket,
        object_key=object_key,
        upload_id=upload_id,
        resource=resource,
    )

    upload_dir = multipart_path(config.MOUNTPOINT_TMP_DIR, upload_id)
    staged_path = os.path.join(config.MOUNTPOINT_TMP_DIR, uuid.uuid4().hex)
    cleanup_dir = None
    object_backup = None
    object_published = False
    objekt = None

    # Lock order: multipart upload dir, then bucket dir. The multipart
    # WRITE lock stays held through publish, commit, and FS rollback.
    async with locks.lock_directory(upload_dir, LockType.WRITE):
        try:
            part_paths, stored_etags = await multipart_parts(
                repo=repo,
                multipart=multipart,
                upload_dir=upload_dir,
                parts=parts,
                resource=resource,
            )

            for part, stored_etag in zip(parts, stored_etags):
                if part.etag != stored_etag:
                    raise S3ObjektPartInvalidError(resource)

            actual_hashes = await concat(part_paths, staged_path)
            for stored_etag, actual_hash in zip(stored_etags, actual_hashes):
                if stored_etag != actual_hash:
                    raise S3ObjektPartInvalidError(resource)

            size_bytes = await get_filesize(staged_path)

            async with locks.lock_directory(bucket_path, LockType.WRITE):
                if not await isdir(bucket_path):
                    raise S3BucketNotFoundError(resource)

                await objekt_mkdir(object_path, resource)

                objekt = await objekt_upsert(
                    repo=repo,
                    bucket=bucket,
                    user=user,
                    object_key=object_key,
                    size_bytes=size_bytes,
                    etag=etag_construct(stored_etags),
                    content_type=multipart.content_type,
                )

                # Keep previous bytes until DB commit. Backup lives next
                # to the object so rename stays atomic on one filesystem.
                if await isfile(object_path):
                    object_backup = os.path.join(
                        os.path.dirname(object_path),
                        f".{os.path.basename(object_path)}."
                        f"{uuid.uuid4().hex}.object.bak",
                    )
                    await rename(object_path, object_backup)

                await rename(staged_path, object_path)
                object_published = True
                staged_path = None

            cleanup_dir = os.path.join(
                config.MOUNTPOINT_TMP_DIR,
                f".{upload_id}.completed.{uuid.uuid4().hex}",
            )
            await rename(upload_dir, cleanup_dir)

            # Parts have no ON DELETE CASCADE; clear them before the
            # parent upload row, then commit.
            await multipart_parts_delete(repo, multipart)
            await repo.delete(multipart)
            await repo.commit()

        except Exception:
            await repo.rollback()

            # Restore object_path and multipart tombstone independently.
            async with locks.lock_directory(bucket_path, LockType.WRITE):
                if object_backup is not None:
                    try:
                        await rename(object_backup, object_path)
                        object_backup = None
                    except Exception:
                        log.exception(
                            "msg=multipart_complete_integrity_failed "
                            "upload_id=%s state=object_backup "
                            "object=%s backup=%s",
                            upload_id,
                            object_path,
                            object_backup,
                        )
                elif object_published:
                    try:
                        await delete(object_path)
                        object_published = False
                    except Exception:
                        log.exception(
                            "msg=multipart_complete_integrity_failed "
                            "upload_id=%s state=published_object "
                            "object=%s",
                            upload_id,
                            object_path,
                        )

            if cleanup_dir is not None:
                try:
                    await rename(cleanup_dir, upload_dir)
                    cleanup_dir = None
                except Exception:
                    log.exception(
                        "msg=multipart_complete_integrity_failed "
                        "upload_id=%s state=multipart_tombstone "
                        "upload_dir=%s cleanup=%s",
                        upload_id,
                        upload_dir,
                        cleanup_dir,
                    )

            if staged_path is not None:
                await delete(staged_path)
            raise

    if object_backup is not None:
        try:
            await delete(object_backup)
        except Exception:
            log.exception(
                "msg=multipart_object_backup_cleanup_failed "
                "upload_id=%s backup=%s",
                upload_id,
                object_backup,
            )

    if cleanup_dir is not None:
        try:
            await rmtree(cleanup_dir)
        except OSError:
            log.exception(
                "msg=multipart_cleanup_failed path=%s",
                cleanup_dir,
            )

    log.info("msg=multipart_completed bucket=%s key=%s", bucket_name, object_key)  # noqa: E501
    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)

    return objekt
