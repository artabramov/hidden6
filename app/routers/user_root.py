# app/routers/user_root.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.require_gocryptfs import require_gocryptfs
from app.dependencies.session import get_session
from app.schemas.user_root import UserRootRequest, UserRootResponse
from app.services.user_root import user_root

router = APIRouter(tags=["users"])


@router.post(
    "/users/root",
    responses={
        401: {
            "description": (
                "Master password is incorrect or the gocryptfs "
                "passphrase cannot be decrypted with it."
            ),
        },
        409: {
            "description": (
                "Root user already exists. Bootstrap is one-time only."
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
                "Encrypted storage is not mounted, not initialized, "
                "or the required gocryptfs passphrase is missing."
            ),
        },
    },
    response_model=UserRootResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_gocryptfs())],
    summary="Create the bootstrap root user (one-time).",
)
async def user_root_router(
    data: UserRootRequest,
    session: AsyncSession = Depends(get_session),
) -> UserRootResponse:
    """
    Creates the root identity principal and its first access key pair.
    Requires the master password and a mounted store. Returns plaintext
    credentials once; subsequent calls conflict.

    `USER_ROOT_CREATED` — hook executed after the root user is created.
    """
    result = await user_root(
        master_password=data.master_password,
        session=session,
    )
    return UserRootResponse(**result)
