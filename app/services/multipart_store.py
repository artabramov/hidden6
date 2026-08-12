# app/services/multipart_store.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from app.errors import S3ObjektUploadNotFoundError
from app.models.bucket import Bucket
from app.models.objekt_multipart import ObjektMultipart
from app.models.user import User
from app.repositories.file import delete, isdir, listdir, rmdir
from app.repositories.orm import ORMRepository
from app.services.objekt_store import load_bucket

log = logging.getLogger(__name__)


# TODO: Expire abandoned multipart uploads, dropping the row and the
# staged parts of an upload that is never completed or aborted.

async def load_multipart(
    repo: ORMRepository,
    bucket_name: str,
    object_key: str,
    user: User,
    upload_id: str,
    resource: str,
    bucket: Bucket | None = None,
) -> ObjektMultipart:
    """
    Load an in-progress upload and check that it belongs to the bucket
    and key being addressed. The caller is authorized against the
    bucket, so the bucket owner and root may upload parts into, finish,
    or abort any upload started in it.
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


def upload_dir(tmp_dir: str, upload_id: str) -> str:
    """
    Return the directory holding the parts of an upload. Uploads are
    staged in the tmp dir next to the bodies of single uploads, each
    one under the upload id issued to the client.
    """
    return os.path.join(tmp_dir, upload_id)


def part_path(upload_dir_path: str, part_number: int) -> str:
    """Return the path of a single staged part."""
    return os.path.join(upload_dir_path, f"part.{part_number:05d}")


async def remove_upload_dir(upload_dir_path: str) -> None:
    """
    Delete the staged parts of an upload and their directory. Cleanup
    runs after the upload has already been completed or aborted, so a
    failure is logged instead of failing the operation.
    """
    try:
        if not await isdir(upload_dir_path):
            return

        for name in await listdir(upload_dir_path):
            await delete(os.path.join(upload_dir_path, name))

        await rmdir(upload_dir_path)

    except OSError:
        log.exception(
            "msg=multipart_cleanup_failed path=%s",
            upload_dir_path,
        )
