# app/routers/gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Response, status

from app.schemas.gocryptfs_init import GocryptfsInitRequest
from app.services.gocryptfs_init import gocryptfs_init

router = APIRouter(tags=["gocryptfs"])


@router.post(
    "/gocryptfs/init",
    responses={
        409: {
            "description": (
                "The gocryptfs cipherdir is already initialized or "
                "required secrets already exist (gocryptfs passphrase "
                "or internal application keys)."
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
    },
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Initialize gocryptfs cipherdir (on first boot).",
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

    `GOCRYPTFS_INITED` — hook executed after the gocryptfs cipherdir
    is successfully initialized.
    """
    await gocryptfs_init(data.master_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
