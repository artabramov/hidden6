# app/routers/gocryptfs_rotate.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_rotate import GocryptfsRotateRequest
from app.services.gocryptfs_rotate import gocryptfs_rotate

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/rotate",
    responses={
        401: {
            "description": (
                "Master password is incorrect or the gocryptfs "
                "passphrase cannot be decrypted with it."
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
    summary="Rotate master password.",
)
async def gocryptfs_rotate_router(
    data: GocryptfsRotateRequest,
) -> Response:
    """
    Rotates the master password that protects the stored gocryptfs
    passphrase. It decrypts the passphrase with the current password
    and encrypts it again with the new password.

    `GOCRYPTFS_ROTATED` — hook executed after the master password
    is successfully rotated.
    """
    await gocryptfs_rotate(
        current_master_password=data.current_master_password,
        changed_master_password=data.changed_master_password,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
