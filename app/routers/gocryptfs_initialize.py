# app/routers/gocryptfs_initialize.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_initialize import GocryptfsInitializeRequest
from app.services.gocryptfs_initialize import initialize_gocryptfs

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/initialize",
    responses={
        409: {
            "description": (
                "Cipherdir is already initialized or required secret "
                "files already exist (gocryptfs passphrase or Fernet "
                "key)."
            ),
        },
        422: {
            # "model": PydanticErrorResponse,
            "description": (
                "Input values failed validation (master password is "
                "missing or does not meet the required length or "
                "strength)."
            ),
        },
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Initialize gocryptfs cipherdir (on first boot)",
)
async def create_cipherdir_router(
    data: GocryptfsInitializeRequest,
) -> Response:
    """
    Initializes encrypted application storage. It generates a strong
    random gocryptfs passphrase, encrypts it with the provided master
    password, and initializes the cipherdir. It also creates internal
    application keys used for JWT signing and symmetric encryption.

    This endpoint is intended for one-time initialization immediately
    after installation.
    """
    await initialize_gocryptfs(data.master_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
