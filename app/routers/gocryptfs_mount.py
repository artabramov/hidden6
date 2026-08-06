# app/routers/gocryptfs_mount.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_mount import GocryptfsMountRequest
from app.services.gocryptfs_mount import gocryptfs_mount

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/mount",
    responses={
        400: {
            "description": (
                "Master password is invalid or encrypted passphrase "
                "cannot be decrypted."
            ),
        },
        404: {
            "description": (
                "Cipherdir is not initialized or gocryptfs passphrase "
                "is not found."
            ),
        },
        409: {
            "description": (
                "Cipherdir is already mounted."
            ),
        },
        422: {
            "description": (
                "Request body failed basic Pydantic validation."
            ),
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mount gocryptfs cipherdir",
)
async def gocryptfs_mount_router(
    data: GocryptfsMountRequest,
) -> Response:
    """
    Mounts encrypted application storage. It decrypts the stored
    gocryptfs passphrase with the provided master password and uses
    it to mount the cipherdir.

    `GOCRYPTFS_MOUNT_COMPLETED` — hook executed after the gocryptfs
    cipherdir is successfully mounted.
    """
    await gocryptfs_mount(
        master_password=data.master_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
