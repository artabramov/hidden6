# app/services/object_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import OBJECT_CONTENT_TYPE_DEFAULT
from app.errors import S3BucketNotFoundError, S3ObjectKeyConflictError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.object import S3Object
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
from app.s3.bucket import load_bucket
from app.s3.object import object_mkdir, upsert_object
from app.s3.paths import resolve_object_path, resolve_staged_path
from app.s3.validation import validate_bucket_name, validate_object_key

log = logging.getLogger(__name__)


# NOTE (ADR-27): S3 empty key directories are kept after rollback.
# Key prefixes are represented as filesystem directories but have no
# independent meaning in the S3 namespace. Tracking and removing
# directories created by a failed operation would complicate filesystem
# reconciliation. Empty directories contain no object data or metadata
# and are therefore accepted as a trade-off for simpler and more
# reliable rollback logic.

# TODO: Add garbage collection for empty S3 key-prefix directories.
# Failed object operations may leave empty filesystem directories that
# represent no state in the S3 namespace. The collector should scan
# bucket trees without holding locks, identify empty directories, then
# acquire the corresponding bucket WRITE lock and attempt removal while
# holding the lock. Removal must rely on rmdir semantics so a directory
# that became non-empty during the scan is left intact. Directories
# should be processed bottom-up, and bucket root directories must never
# be removed.

# TODO: Add S3 object versioning to the upload transaction.
#
# PUT Object behavior depends on the bucket versioning state and on the
# version ID of the current object state.
#
# Disabled:
#     Keep the current behavior. The object has the S3 null version
#     (internally version_id = NULL), PUT replaces it in place, and no
#     historical ObjectVersion row is created.
#
# Enabled:
#     Every PUT creates a new current object state with a unique
#     version_id. If a current state already exists, preserve it as an
#     ObjectVersion before publishing the new payload. This also applies
#     to objects that predate versioning and therefore have a null
#     version ID: the old null version becomes noncurrent and the new
#     current state receives a unique version ID.
#
#     If the current state is a delete marker, preserve the marker as a
#     noncurrent ObjectVersion and publish the new object as the current
#     version. Delete markers have metadata but no payload to preserve.
#
# Suspended:
#     Every new PUT creates the S3 null version (version_id = NULL).
#
#     If the current state has a unique version ID, preserve it as a
#     noncurrent ObjectVersion and publish a new null current version.
#
#     If the current state is already the null version, overwrite that
#     null version in place. It must not be retained as another
#     ObjectVersion because S3 keeps at most one null version per key.
#
#     If the current state is a uniquely identified delete marker,
#     preserve the marker as a noncurrent ObjectVersion and publish a
#     new null current version.
#
#     If the current state is a null delete marker, replace the marker
#     with the new null object state rather than retaining the marker as
#     history.
#
# Filesystem and DB changes must remain one compensated transaction:
# current payloads that become noncurrent must be moved/copied to the
# versions store before the canonical bucket/key path is replaced, while
# delete markers require only DB history. Rollback must restore both the
# previous current metadata and its payload when applicable.
#
# A successful PUT should return the new current version ID through
# x-amz-version-id when versioning is Enabled or Suspended. Disabled
# buckets expose the null version without a version header.

async def object_upload(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    object_key: str,
    body: AsyncReadable,
) -> S3Object:
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
    resource = f"/{bucket_name}/{object_key}"

    validate_bucket_name(bucket_name, resource)
    validate_object_key(object_key, resource)

    bucket_path, object_path = resolve_object_path(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        object_key,
    )

    repo = ORMRepository(session)
    bucket = await load_bucket(repo, bucket_name, current_user, resource)

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
    object_written = False

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

            await object_mkdir(object_path, resource)

            # Preserve the current payload in tmp before overwriting it.
            # A copy keeps the canonical object path intact until the
            # new payload is ready to replace it.
            if await isfile(object_path):
                await copy(object_path, backup_path)
                backup_created = True

            s3_object = await upsert_object(
                repo=repo,
                bucket=bucket,
                user=current_user,
                object_key=object_key,
                size_bytes=size_bytes,
                etag=etag,
                content_type=content_type or OBJECT_CONTENT_TYPE_DEFAULT,
            )

            try:
                await rename(staged_path, object_path)
            except (IsADirectoryError, NotADirectoryError) as exc:
                raise S3ObjectKeyConflictError(resource) from exc

            object_written = True
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
                    object_key,
                )

            # A new object was published before the transaction failed.
            # Remove it because there is no previous payload to restore.
            if object_written and not backup_created:
                try:
                    await delete(object_path)
                except Exception:
                    log.exception(
                        "msg=cleanup_failed "
                        "object_path=%s",
                        object_path,
                    )

            # An existing object was overwritten before the transaction
            # failed. Restore its previous payload from the temporary
            # backup.
            if object_written and backup_created:
                try:
                    await copy(backup_path, object_path)
                except Exception:
                    log.exception(
                        "msg=restore_failed "
                        "bucket_name=%s "
                        "object_key=%s",
                        bucket_name,
                        object_key,
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
            if backup_created and not object_written:
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

    await hooks.emit(Events.OBJECT_UPLOADED, s3_object)
    return s3_object
