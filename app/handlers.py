# app/handlers.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import Request, status
from fastapi.responses import Response

from app.errors import (
    InternalServerError,
    BadRequestError,
    ResourceNotFoundError,
    ResourceConflictError,
)


async def internal_server_error_handler(
    request: Request,
    exc: InternalServerError,
) -> Response:
    return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def bad_request_handler(
    request: Request,
    exc: BadRequestError,
) -> Response:
    return Response(status_code=status.HTTP_400_BAD_REQUEST)


async def resource_not_found_handler(
    request: Request,
    exc: ResourceNotFoundError,
) -> Response:
    return Response(status_code=status.HTTP_404_NOT_FOUND)


async def resource_conflict_handler(
    request: Request,
    exc: ResourceConflictError,
) -> Response:
    return Response(status_code=status.HTTP_409_CONFLICT)
