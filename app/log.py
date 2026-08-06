# app/log.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import sys

from app.config import get_config
from app.context import get_context_var


class RequestContextFilter(logging.Filter):
    """
    Inject request-scoped context values into log records.
    Adds fields expected by the log format (e.g. request_uuid).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Populate the log record with values from the current context.
        Always returns True to allow the record to be processed.
        """
        record.request_uuid = get_context_var("request_uuid", "-")
        return True


def init_logging() -> None:
    """
    Initialize root logger with configured level, format and handlers.
    Replaces existing handlers and attaches a stream handler with
    request context enrichment.
    """
    config = get_config()

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    formatter = logging.Formatter(fmt=config.LOG_FORMAT)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
