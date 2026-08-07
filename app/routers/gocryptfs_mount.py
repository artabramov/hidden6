# app/routers/gocryptfs_mount.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_mount import GocryptfsMountRequest
from app.services.gocryptfs_mount import gocryptfs_mount

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/mount",
    responses={
        401: {
            "description": (
                "Master password is incorrect or the gocryptfs "
                "passphrase cannot be decrypted with it."
            ),
        },
        409: {
            "description": (
                "The gocryptfs cipherdir is already mounted. "
                "The requested operation is unnecessary."
            ),
        },
        422: {
            "description": (
                "Request body failed basic Pydantic validation. "
                "This includes type validation, field constraints, "
                "and custom validators."
            ),
        },
        500: {
            "description": (
                "An unexpected internal error occurred while handling "
                "the request. The operation could not be completed."
            ),
        },
        503: {
            "description": (
                "The gocryptfs cipherdir is not initialized or "
                "unavailable, or the required gocryptfs passphrase "
                "is missing."
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
    that passphrase to mount the cipherdir.

    `GOCRYPTFS_MOUNT_COMPLETED` — hook executed after the gocryptfs
    cipherdir is successfully mounted.
    """
    await gocryptfs_mount(master_password=data.master_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
