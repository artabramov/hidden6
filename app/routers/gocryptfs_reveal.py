# app/routers/gocryptfs_reveal.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, status

from app.schemas.gocryptfs_reveal import (
    GocryptfsRevealRequest,
    GocryptfsRevealResponse,
)
from app.services.gocryptfs_reveal import gocryptfs_reveal

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/reveal",
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
                "Gocryptfs infrastructure is not ready: cipherdir "
                "is not initialized, not mounted, or the required "
                "passphrase is missing."
            ),
        },
    },
    response_model=GocryptfsRevealResponse,
    status_code=status.HTTP_200_OK,
    summary="Reveal gocryptfs passphrase.",
)
async def gocryptfs_reveal_router(
    data: GocryptfsRevealRequest,
) -> GocryptfsRevealResponse:
    """
    Decrypts the stored gocryptfs passphrase with the provided master
    password and returns it in the response body.

    `GOCRYPTFS_REVEALED` — hook executed after the gocryptfs passphrase
    is successfully revealed.
    """
    passphrase = await gocryptfs_reveal(
        master_password=data.master_password,
    )
    return GocryptfsRevealResponse(
        gocryptfs_passphrase=passphrase,
    )
