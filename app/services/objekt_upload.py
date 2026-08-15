# app/services/objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJEKT_CONTENT_TYPE_DEFAULT
from app.errors import S3BucketNotFoundError, S3ObjektKeyConflictError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import (
    AsyncReadable,
    copy,
    delete,
    get_file_hash,
    get_filesize,
    get_mimetype,
    isdir,
    isfile,
    rename,
    upload,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket import bucket_load
from app.s3.objekt import objekt_mkdir, objekt_upsert
from app.s3.paths import resolve_objekt_path, resolve_staged_path
from app.s3.validation import validate_bucket_name, validate_objekt_key

log = logging.getLogger(__name__)


# NOTE (ADR-28): S3 object operations may leave empty key directories.
# Key prefixes are represented as filesystem directories but have no
# independent meaning in the S3 namespace. Tracking and removing
# directories created by a failed operation would complicate filesystem
# reconciliation. Empty directories contain no object data or metadata
# and are therefore accepted as a trade-off for simpler and more
# reliable rollback logic.

async def objekt_upload(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    objekt_key: str,
    body: AsyncReadable,
) -> Objekt:
    """
    Upload an S3 object to the specified bucket. The operation is
    transactional at the DB level and reconciles filesystem state
    on failure. All writes are staged through a temporary file and
    applied under a bucket directory lock.

    (1) verify that the bucket directory exists
    (2) upload object data to a temporary path
    (3) read object metadata (size, ETag, content type)
    (4) create the directories carrying the object key prefix

    if object exists:
        (5) copy the current object as a restore source

    (6) create or update the object record
    (7) publish the staged object
    (8) commit

    On failure of the main transaction, the session is rolled back
    and filesystem state is reconciled: staged data is removed, newly
    written objects are deleted, or overwritten objects are restored
    from the temporary backup.

    After a successful commit, the temporary backup is removed as a
    best-effort cleanup step.
    """
    config = get_config()
    resource = f"/{bucket_name}/{objekt_key}"

    validate_bucket_name(bucket_name, resource)
    validate_objekt_key(objekt_key, resource)

    bucket_path, objekt_path = resolve_objekt_path(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        objekt_key,
    )

    repo = ORMRepository(session)
    bucket = await bucket_load(repo, bucket_name, current_user, resource)

    # Temporary path used to stage the incoming object
    # before it is published to the bucket.
    staged_path = resolve_staged_path(
        config.MOUNTPOINT_TMP_DIR,
        uuid.uuid4().hex,
    )

    # Temporary path used to preserve the existing object
    # so it can be restored if the upload fails.
    backup_path = resolve_staged_path(
        config.MOUNTPOINT_TMP_DIR,
        uuid.uuid4().hex,
    )

    backup_created = False
    objekt_written = False

    # The whole bucket subtree is locked for the upload transaction
    # because a conflicting key can sit at any prefix level.
    async with locks.lock_directory(bucket_path, LockType.WRITE):
        try:
            if not await isdir(bucket_path):
                raise S3BucketNotFoundError(resource)

            # Staging is intentionally kept under the same lock to keep
            # publishing and filesystem reconciliation in one linear
            # transaction scope.
            await upload(body, staged_path)
            size_bytes = await get_filesize(staged_path)
            etag = await get_file_hash(staged_path)
            content_type = await get_mimetype(staged_path)

            await objekt_mkdir(objekt_path, resource)

            # Preserve the current payload in tmp before overwriting it.
            # A copy keeps the canonical object path intact until the
            # new payload is ready to replace it.
            if await isfile(objekt_path):
                await copy(objekt_path, backup_path)
                backup_created = True

            objekt = await objekt_upsert(
                repo=repo,
                bucket=bucket,
                user=current_user,
                object_key=objekt_key,
                size_bytes=size_bytes,
                etag=etag,
                content_type=content_type or OBJEKT_CONTENT_TYPE_DEFAULT,
            )

            try:
                await rename(staged_path, objekt_path)
            except (IsADirectoryError, NotADirectoryError) as exc:
                raise S3ObjektKeyConflictError(resource) from exc

            objekt_written = True
            await repo.commit()

        # Reconcile DB and filesystem state before releasing the bucket
        # lock, so no request can observe an intermediate state.
        except Exception:
            try:
                await repo.rollback()
            except Exception:
                log.exception(
                    "msg=rollback_failed "
                    "bucket_name=%s "
                    "object_key=%s",
                    bucket_name,
                    objekt_key,
                )

            # A new object was published before the transaction failed.
            # Remove it because there is no previous payload to restore.
            if objekt_written and not backup_created:
                try:
                    await delete(objekt_path)
                except Exception:
                    log.exception(
                        "msg=cleanup_failed "
                        "objekt_path=%s",
                        objekt_path,
                    )

            # An existing object was overwritten before the transaction
            # failed. Restore its previous payload from the temporary
            # backup.
            if objekt_written and backup_created:
                try:
                    await copy(backup_path, objekt_path)
                except Exception:
                    log.exception(
                        "msg=restore_failed "
                        "bucket_name=%s "
                        "object_key=%s",
                        bucket_name,
                        objekt_key,
                    )
                else:
                    # The previous payload is back in place,
                    # so the backup is no longer needed.
                    try:
                        await delete(backup_path)
                    except Exception:
                        log.exception(
                            "msg=cleanup_failed "
                            "backup_path=%s",
                            backup_path,
                        )

            # A backup was created, but the new payload was never
            # published. The original object is still intact, so
            # discard the backup.
            if backup_created and not objekt_written:
                try:
                    await delete(backup_path)
                except Exception:
                    log.exception(
                        "msg=cleanup_failed "
                        "backup_path=%s",
                        backup_path,
                    )

            # Remove any staged payload left behind
            # by a failed upload.
            try:
                await delete(staged_path)
            except Exception:
                log.exception(
                    "msg=cleanup_failed "
                    "staged_path=%s",
                    staged_path,
                )

            raise

    # After a successful commit, the previous payload
    # is no longer needed.
    if backup_created:
        try:
            await delete(backup_path)
        except Exception:
            log.exception(
                "msg=cleanup_failed "
                "backup_path=%s",
                backup_path,
            )

    await hooks.emit(Events.OBJEKT_UPLOADED, objekt)
    return objekt
