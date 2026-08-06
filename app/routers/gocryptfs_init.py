# app/routers/gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_init import GocryptfsInitRequest
from app.schemas.pydantic_error import PydanticErrorResponse
from app.services.gocryptfs_init import gocryptfs_init

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/init",
    responses={
        409: {
            "description": (
                "Cipherdir is already initialized or required secret "
                "files already exist (gocryptfs passphrase or Fernet "
                "key)."
            ),
        },
        422: {
            "model": PydanticErrorResponse,
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
async def gocryptfs_init_router(
    data: GocryptfsInitRequest,
) -> Response:
    """
    Initializes encrypted application storage. It generates a strong
    random gocryptfs passphrase, encrypts it with the provided master
    password, and initializes the cipherdir. It also creates internal
    application keys used for symmetric encryption.

    This endpoint is intended for one-time initialization immediately
    after installation.
    """
    await gocryptfs_init(data.master_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
