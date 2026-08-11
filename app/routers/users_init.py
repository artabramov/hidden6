# app/routers/users_init.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.require_session import require_session
from app.schemas.users_init import UsersInitRequest, UsersInitResponse
from app.services.users_init import users_init

router = APIRouter(tags=["users"])


@router.post(
    "/users/init",
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
    response_model=UsersInitResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_gocryptfs())],
    summary="Initialize root user (one-time).",
)
async def users_init_router(
    data: UsersInitRequest,
    session: AsyncSession = Depends(require_session),
) -> UsersInitResponse:
    """
    Initializes identity by creating the root user and its first
    access key pair. Requires the master password and a mounted store.
    Returns plaintext credentials once; subsequent calls conflict.

    `USERS_INITIALIZED` — hook executed after users initialization.
    """
    result = await users_init(
        master_password=data.master_password,
        session=session,
    )
    return UsersInitResponse(**result)
