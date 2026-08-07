# app/routers/gocryptfs_passphrase.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, status

from app.schemas.gocryptfs_passphrase import (
    GocryptfsPassphraseRequest,
    GocryptfsPassphraseResponse,
)
from app.services.gocryptfs_passphrase import gocryptfs_passphrase

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/passphrase",
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
    response_model=GocryptfsPassphraseResponse,
    status_code=status.HTTP_200_OK,
    summary="Reveal gocryptfs passphrase.",
)
async def gocryptfs_passphrase_router(
    data: GocryptfsPassphraseRequest,
) -> GocryptfsPassphraseResponse:
    """
    Decrypts the stored gocryptfs passphrase with the provided master
    password and returns it in the response body.
    """
    passphrase = await gocryptfs_passphrase(
        master_password=data.master_password,
    )
    return GocryptfsPassphraseResponse(
        gocryptfs_passphrase=passphrase,
    )
