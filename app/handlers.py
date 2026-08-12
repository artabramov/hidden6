# app/handlers.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import Request, status
from fastapi.responses import Response

from app.context import get_context_var
from app.errors import (
    UnauthorizedError,
    InternalServerError,
    ServiceUnavailableError,
    BadGatewayError,
    S3Error,
)
from app.xml.render_error import render_error


async def unauthorized_handler(
    request: Request,
    exc: UnauthorizedError,
) -> Response:
    return Response(status_code=status.HTTP_401_UNAUTHORIZED)


async def internal_server_error_handler(
    request: Request,
    exc: InternalServerError,
) -> Response:
    return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def bad_gateway_handler(
    request: Request,
    exc: BadGatewayError,
) -> Response:
    return Response(status_code=status.HTTP_502_BAD_GATEWAY)


async def service_unavailable_handler(
    request: Request,
    exc: ServiceUnavailableError,
) -> Response:
    return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


async def s3_error_handler(
    request: Request,
    exc: S3Error,
) -> Response:
    request_id = get_context_var("request_uuid", "-")

    return Response(
        content=render_error(exc, str(request_id)),
        status_code=exc.status_code,
        media_type="application/xml",
    )
