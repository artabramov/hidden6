# app/s3/object_version.py
# SPDX-License-Identifier: GPL-3.0-only

from app.models.object import S3Object
from app.models.object_metadata import S3ObjectMetadata
from app.models.object_tag import S3ObjectTag
from app.models.object_version import S3ObjectVersion
from app.models.object_version_metadata import S3ObjectVersionMetadata
from app.models.object_version_tag import S3ObjectVersionTag
from app.repositories.orm import ORMRepository


async def create_object_version(
    repo: ORMRepository,
    s3_object: S3Object,
) -> S3ObjectVersion:
    """
    Preserve the current object state as a noncurrent version.

    The object row, metadata, and tags are copied to version history.
    The returned version row is flushed so its internal ID can be used
    to address the retained payload in version storage.
    """
    version = await repo.insert(
        S3ObjectVersion(
            object_id=s3_object.id,
            user_id=s3_object.user_id,
            modified_at=s3_object.modified_at,
            version_uuid=s3_object.version_uuid,
            size_bytes=s3_object.size_bytes,
            etag=s3_object.etag,
            content_type=s3_object.content_type,
            delete_marker=s3_object.delete_marker,
            lock_mode=s3_object.lock_mode,
            retain_until=s3_object.retain_until,
            legal_hold=s3_object.legal_hold,
        ),
    )

    # Preserve the current object metadata.
    metadata_rows = await repo.select_all(
        S3ObjectMetadata,
        object_id=s3_object.id,
    )

    for row in metadata_rows:
        await repo.insert(
            S3ObjectVersionMetadata(
                object_version_id=version.id,
                meta_key=row.meta_key,
                meta_value=row.meta_value,
            ),
            flush=False,
        )

    # Preserve the current object tags.
    tag_rows = await repo.select_all(
        S3ObjectTag,
        object_id=s3_object.id,
    )

    for row in tag_rows:
        await repo.insert(
            S3ObjectVersionTag(
                object_version_id=version.id,
                tag_key=row.tag_key,
                tag_value=row.tag_value,
            ),
            flush=False,
        )

    # Flush the related version state in one batch.
    await repo.flush()
    return version
