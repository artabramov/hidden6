# app/routers/gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_unmount import GocryptfsUnmountRequest
from app.services.gocryptfs_unmount import gocryptfs_unmount

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/unmount",
    responses={
        401: {
            "description": (
                "Master password is incorrect or the gocryptfs "
                "passphrase cannot be decrypted with it."
            ),
        },
        409: {
            "description": (
                "The gocryptfs cipherdir is not mounted. "
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
    summary="Unmount gocryptfs cipherdir.",
)
async def gocryptfs_unmount_router(
    data: GocryptfsUnmountRequest,
) -> Response:
    """
    Unmounts encrypted application storage. It verifies the master
    password by decrypting the stored gocryptfs passphrase, then
    unmounts the cipherdir.

    `GOCRYPTFS_UNMOUNTED` — hook executed after the gocryptfs cipherdir
    is successfully unmounted.
    """
    await gocryptfs_unmount(master_password=data.master_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
