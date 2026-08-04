# app/handlers.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import Request, status
from fastapi.responses import Response

from app.errors import InternalServerError, ResourceConflictError


async def internal_server_error_handler(
    request: Request,
    exc: InternalServerError,
) -> Response:
    return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def resource_conflict_handler(
    request: Request,
    exc: ResourceConflictError,
) -> Response:
    return Response(status_code=status.HTTP_409_CONFLICT)
