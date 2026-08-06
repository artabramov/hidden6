# app/routers/gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_init import GocryptfsInitRequest
from app.services.gocryptfs_init import gocryptfs_init

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/init",
    responses={
        400: {
            "description": (
                "Master password does not meet the required strength: "
                "it must contain at least one lowercase letter, one "
                "uppercase letter, and one digit."
            ),
        },
        409: {
            "description": (
                "Cipherdir is already initialized or required secret "
                "files already exist (gocryptfs passphrase or Fernet "
                "key)."
            ),
        },
        422: {
            "description": (
                "Request body failed basic Pydantic validation."
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
