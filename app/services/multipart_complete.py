# app/services/multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.errors import (
    S3BucketNotFoundError,
    S3ObjectKeyConflictError,
    S3ObjectPartInvalidError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.objekt import Objekt
from app.models.user import User
from app.repositories.io import (
    concat,
    copy,
    delete,
    get_filesize,
    isdir,
    isfile,
    rename,
    rmtree,
)
from app.repositories.orm import ORMRepository
from app.s3.bucket import load_bucket
from app.s3.etag import construct_etag
from app.s3.multipart import (
    load_multipart,
    load_multipart_parts,
    delete_multipart_parts,
)
from app.s3.object import object_mkdir, upsert_object
from app.s3.paths import (
    resolve_multipart_completed_path,
    resolve_multipart_object_backup_path,
    resolve_multipart_path,
    resolve_objekt_path,
    resolve_staged_path,
)
from app.s3.validation import validate_bucket_name, validate_objekt_key
from app.schemas.multipart_complete import MultipartPart

log = logging.getLogger(__name__)


async def multipart_complete(
    session: AsyncSession,
    current_user: User,
    bucket_name: str,
    objekt_key: str,
    upload_id: str,
    parts: list[MultipartPart],
) -> Objekt:
    """
    Complete an S3 multipart upload. The uploaded parts are validated
    and assembled into a staged object while the multipart upload is
    locked. The completed object is then published under the bucket
    WRITE lock and committed together with removal of the multipart
    upload state.

    (1) load the multipart upload
    (2) load and validate the requested parts
    (3) assemble the parts into a temporary object
    (4) verify the stored part ETags against the assembled data
    (5) read the assembled object size
    (6) verify that the bucket directory exists
    (7) create the directories carrying the object key prefix

    if object exists:
        (8) copy the current object to a temporary backup

    (9) publish the assembled object
    (10) move the multipart upload to a temporary cleanup path
    (11) delete all multipart part records
    (12) delete the multipart upload record
    (13) commit

    On failure during assembly, staged object data is removed.
    On failure during publication, the session is rolled back and
    filesystem state is reconciled: newly written objects are removed,
    overwritten objects are restored from their temporary backup, the
    active multipart upload is restored from its cleanup path, and
    staged data is removed.

    After a successful commit, the previous object backup and completed
    multipart upload directory are removed as best-effort cleanup steps.
    """
    config = get_config()
    resource = f"/{bucket_name}/{objekt_key}"

    validate_bucket_name(bucket_name, resource)
    validate_objekt_key(objekt_key, resource)

    bucket_path, object_path = resolve_objekt_path(
        config.MOUNTPOINT_BUCKETS_DIR,
        bucket_name,
        objekt_key,
    )

    repo = ORMRepository(session)
    bucket = await load_bucket(repo, bucket_name, current_user, resource)

    # Path containing the active multipart upload
    # and its uploaded parts.
    upload_path = resolve_multipart_path(
        config.MOUNTPOINT_TMP_DIR,
        upload_id,
    )

    # Temporary path used to assemble the uploaded parts
    # before the completed object is published.
    staged_path = resolve_staged_path(
        config.MOUNTPOINT_TMP_DIR,
        uuid.uuid4().hex,
    )

    # Temporary path used to move the completed multipart
    # upload aside until the transaction is committed.
    cleanup_path = resolve_multipart_completed_path(
        config.MOUNTPOINT_TMP_DIR,
        upload_id,
        uuid.uuid4().hex,
    )

    # Temporary path used to preserve the existing object
    # so it can be restored if completion fails.
    backup_path = resolve_multipart_object_backup_path(
        config.MOUNTPOINT_TMP_DIR,
        uuid.uuid4().hex,
    )

    backup_created = False
    objekt_written = False
    upload_moved = False

    # Hold the multipart lock through validation, assembly, publication,
    # and commit so UploadPart cannot change the source parts.
    async with locks.lock_directory(upload_path, LockType.WRITE):
        try:
            multipart = await load_multipart(
                repo=repo,
                bucket=bucket,
                object_key=objekt_key,
                upload_id=upload_id,
                resource=resource,
            )

            # Part validation and assembly may require reading the
            # entire multipart payload. Keep this expensive work outside
            # the bucket lock so other operations on the bucket are not
            # blocked while the object is assembled.
            part_paths, stored_etags = await load_multipart_parts(
                repo=repo,
                multipart=multipart,
                upload_path=upload_path,
                parts=parts,
                resource=resource,
            )

            for part, stored_etag in zip(parts, stored_etags):
                if part.etag != stored_etag:
                    raise S3ObjectPartInvalidError(resource)

            actual_hashes = await concat(part_paths, staged_path)
            for stored_etag, actual_hash in zip(stored_etags, actual_hashes):
                if stored_etag != actual_hash:
                    raise S3ObjectPartInvalidError(resource)

            size_bytes = await get_filesize(staged_path)

        except Exception:
            try:
                await repo.rollback()
            except Exception:
                log.exception(
                    "msg=rollback_failed "
                    "bucket_name=%s "
                    "object_key=%s "
                    "upload_id=%s",
                    bucket_name,
                    objekt_key,
                    upload_id,
                )

            # Remove any assembled payload left behind by
            # the failed completion.
            try:
                await delete(staged_path)
            except Exception:
                log.exception(
                    "msg=cleanup_failed "
                    "staged_path=%s",
                    staged_path,
                )

            raise

        # The bucket lock is acquired only for publication and held
        # through commit and filesystem compensation.
        async with locks.lock_directory(bucket_path, LockType.WRITE):
            try:
                if not await isdir(bucket_path):
                    raise S3BucketNotFoundError(resource)

                await object_mkdir(object_path, resource)

                objekt = await upsert_object(
                    repo=repo,
                    bucket=bucket,
                    user=current_user,
                    object_key=objekt_key,
                    size_bytes=size_bytes,
                    etag=construct_etag(stored_etags),
                    content_type=multipart.content_type,
                )

                # Backing up an existing object requires copying its
                # full payload under the bucket WRITE lock. This cost
                # is accepted to preserve the previous object until
                # the transaction commits or can be rolled back.
                if await isfile(object_path):
                    await copy(object_path, backup_path)
                    backup_created = True

                try:
                    await rename(staged_path, object_path)
                except (IsADirectoryError, NotADirectoryError) as exc:
                    raise S3ObjectKeyConflictError(resource) from exc
                objekt_written = True

                await rename(upload_path, cleanup_path)
                upload_moved = True

                # Parts have no ON DELETE CASCADE; clear them before
                # the parent upload row, then commit.
                await delete_multipart_parts(repo, multipart)
                await repo.delete(multipart)
                await repo.commit()

            except Exception:
                try:
                    await repo.rollback()
                except Exception:
                    log.exception(
                        "msg=rollback_failed "
                        "bucket_name=%s "
                        "object_key=%s "
                        "upload_id=%s",
                        bucket_name,
                        objekt_key,
                        upload_id,
                    )

                # A new object was published before the transaction
                # failed. Remove it because there is no previous
                # payload to restore.
                if objekt_written and not backup_created:
                    try:
                        await delete(object_path)
                    except Exception:
                        log.exception(
                            "msg=cleanup_failed "
                            "object_path=%s",
                            object_path,
                        )

                # An existing object was overwritten before the
                # transaction failed. Restore its previous payload
                # from the temporary backup.
                if objekt_written and backup_created:
                    try:
                        await copy(backup_path, object_path)
                    except Exception:
                        log.exception(
                            "msg=restore_failed "
                            "object_path=%s "
                            "backup_path=%s",
                            object_path,
                            backup_path,
                        )
                    else:
                        try:
                            await delete(backup_path)
                        except Exception:
                            log.exception(
                                "msg=cleanup_failed "
                                "backup_path=%s",
                                backup_path,
                            )

                # A backup was created, but the assembled object was
                # never published. The original object is still intact,
                # so discard the backup.
                if backup_created and not objekt_written:
                    try:
                        await delete(backup_path)
                    except Exception:
                        log.exception(
                            "msg=cleanup_failed "
                            "backup_path=%s",
                            backup_path,
                        )

                # The active multipart upload was moved aside before the
                # transaction failed. Restore it from the cleanup path.
                if upload_moved:
                    try:
                        await rename(cleanup_path, upload_path)
                    except Exception:
                        log.exception(
                            "msg=restore_failed "
                            "upload_path=%s "
                            "cleanup_path=%s",
                            upload_path,
                            cleanup_path,
                        )

                # Remove any assembled payload left behind by
                # the failed completion.
                try:
                    await delete(staged_path)
                except Exception:
                    log.exception(
                        "msg=cleanup_failed "
                        "staged_path=%s",
                        staged_path,
                    )

                raise

    # After a successful commit, the previous
    # object backup is no longer needed.
    if backup_created:
        try:
            await delete(backup_path)
        except Exception:
            log.exception(
                "msg=cleanup_failed "
                "backup_path=%s",
                backup_path,
            )

    # After a successful commit, the completed multipart
    # upload directory is no longer needed.
    if upload_moved:
        try:
            await rmtree(cleanup_path)
        except Exception:
            log.exception(
                "msg=cleanup_failed "
                "cleanup_path=%s",
                cleanup_path,
            )

    await hooks.emit(Events.OBJECT_UPLOADED, objekt)
    return objekt
