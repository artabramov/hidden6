# app/routers/user_init.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.schemas.user_init import UserInitRequest, UserInitResponse
from app.services.user_init import user_init

router = APIRouter(tags=["users"])


@router.post(
    "/user/init",
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
        502: {
            "description": (
                "Root user already exists. Bootstrap is one-time only."
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
    response_model=UserInitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_gocryptfs())],
    summary="Initialize root user (one-time).",
)
async def user_init_router(
    data: UserInitRequest,
    session: AsyncSession = Depends(require_session),
) -> UserInitResponse:
    """
    Initializes identity by creating the root user and its first
    access key pair. Requires the master password and a mounted store.
    Returns plaintext credentials once; subsequent calls conflict.

    `USER_INITIALIZED` — hook executed after user initialization.
    """
    result = await user_init(
        master_password=data.master_password,
        session=session,
    )
    return UserInitResponse(**result)
