# app/routers/gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_unmount import GocryptfsUnmountRequest
from app.services.gocryptfs_unmount import gocryptfs_unmount

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/unmount",
    responses={
        400: {
            "description": (
                "Master password is invalid or encrypted passphrase "
                "cannot be decrypted."
            ),
        },
        404: {
            "description": (
                "Cipherdir is not initialized or encrypted passphrase "
                "file is missing."
            ),
        },
        409: {
            "description": (
                "Cipherdir is not mounted."
            ),
        },
        422: {
            "description": (
                "Request body failed basic Pydantic validation."
            ),
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unmount gocryptfs cipherdir",
)
async def gocryptfs_unmount_router(
    data: GocryptfsUnmountRequest,
) -> Response:
    """
    Unmounts encrypted application storage. It verifies the master
    password by decrypting the stored gocryptfs passphrase, then
    unmounts the cipherdir.

    `GOCRYPTFS_UNMOUNT_COMPLETED` — hook executed after the gocryptfs
    cipherdir is successfully unmounted.
    """
    await gocryptfs_unmount(master_password=data.master_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
