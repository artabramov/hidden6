# app/s3/multipart_cleanup.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from app.repositories.file import delete, isdir, listdir, rmdir

log = logging.getLogger(__name__)


# TODO: Expire abandoned multipart uploads, dropping the row and the
# staged parts of an upload that is never completed or aborted.

async def multipart_cleanup(upload_dir: str) -> None:
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
        log.exception("msg=multipart_cleanup_failed path=%s", upload_dir)
