# app/s3/objekt_mkdir.py
# SPDX-License-Identifier: GPL-3.0-only

import os

from app.errors import S3ObjektKeyConflictError
from app.repositories.file import isdir, mktree


async def objekt_mkdir(object_path: str, resource: str) -> None:
    """
    Create the directories carrying the key prefix. A prefix occupied
    by a stored object cannot become a directory, and neither can a
    key already used by a directory hold an object.
    """
    if await isdir(object_path):
        raise S3ObjektKeyConflictError(resource)

    try:
        await mktree(os.path.dirname(object_path))
    except (FileExistsError, NotADirectoryError) as exc:
        raise S3ObjektKeyConflictError(resource) from exc
