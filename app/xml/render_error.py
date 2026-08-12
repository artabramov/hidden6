# app/xml/render_error.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from app.errors import S3Error


def render_error(exc: S3Error, request_id: str) -> str:
    """
    Render an S3-compatible XML error response, carrying the error code
    and message plus the request id that correlates the failure with the
    application log. The resource is omitted when the failing operation
    addresses no bucket or object.
    """
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<Error>",
        f"<Code>{escape(exc.code)}</Code>",
        f"<Message>{escape(exc.message)}</Message>",
    ]
    if exc.resource:
        parts.append(f"<Resource>{escape(exc.resource)}</Resource>")

    parts.extend([
        f"<RequestId>{escape(request_id)}</RequestId>",
        "</Error>",
    ])
    return "".join(parts)
