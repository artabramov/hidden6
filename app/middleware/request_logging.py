# app/middleware/request_logging.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import time

from fastapi import Request

from app.context import get_context_var

logger = logging.getLogger(__name__)


async def request_logging_middleware(request: Request, call_next):
    """
    Emits logs for request start, completion and failure,
    including basic metadata and elapsed time.
    """
    client = request.client.host if request.client else None
    logger.info(
        "msg=request_started method=%s url=%s client=%s",
        request.method,
        request.url,
        client,
    )

    try:
        response = await call_next(request)

        start_time = get_context_var("request_start_time")
        elapsed_time = time.perf_counter() - start_time
        logger.info(
            "msg=request_finished status_code=%s elapsed_time=%.6f",
            response.status_code,
            elapsed_time,
        )

    except Exception:
        logger.exception("msg=request_failed")
        raise

    return response
