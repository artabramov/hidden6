# app/handlers.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from fastapi import Request, status
from fastapi.responses import Response

from app.context import get_context_var
from app.errors import (
    UnauthorizedError,
    ForbiddenError,
    ResourceConflictError,
    InternalServerError,
    ServiceUnavailableError,
    BadGatewayError,
    S3Error,
)


async def unauthorized_handler(
    request: Request,
    exc: UnauthorizedError,
) -> Response:
    return Response(status_code=status.HTTP_401_UNAUTHORIZED)


async def forbidden_handler(
    request: Request,
    exc: ForbiddenError,
) -> Response:
    return Response(status_code=status.HTTP_403_FORBIDDEN)


async def resource_conflict_handler(
    request: Request,
    exc: ResourceConflictError,
) -> Response:
    return Response(status_code=status.HTTP_409_CONFLICT)


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
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<Error>",
        f"<Code>{escape(exc.code)}</Code>",
        f"<Message>{escape(exc.message)}</Message>",
    ]
    if exc.resource:
        parts.append(f"<Resource>{escape(exc.resource)}</Resource>")
    parts.append(f"<RequestId>{escape(str(request_id))}</RequestId>")
    parts.append("</Error>")

    return Response(
        content="".join(parts),
        status_code=exc.status_code,
        media_type="application/xml",
    )
