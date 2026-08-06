# app/main.py
# SPDX-License-Identifier: GPL-3.0-only

from contextlib import asynccontextmanager
from starlette.middleware.gzip import GZipMiddleware
from fastapi import FastAPI

from app.version import __version__
from app.config import get_config
from app.log import init_logging

from app.errors import (
    InternalServerError,
    ResourceConflictError,
)

from app.handlers import (
    internal_server_error_handler,
    resource_conflict_handler,
)

from app.middleware.cors_setup import cors_setup_middleware
from app.middleware.request_context import request_context_middleware
from app.middleware.request_logging import request_logging_middleware
from app.middleware.security_headers import security_headers_middleware

from app.routers.gocryptfs_init import router as gocryptfs_init

config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logging()
    yield


app = FastAPI(
    version=__version__,
    lifespan=lifespan,
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    }
)

# NOTE (ADR-XX): Middleware order is intentionally fixed.
# The order is intentional and must not be changed. Request context
# is initialized before other middleware and reset only after the full
# request lifecycle completes. Downstream middleware (e.g. request
# logging) depends on this. This is an architectural constraint, not
# an implementation detail.

app.middleware("http")(request_logging_middleware)
app.middleware("http")(request_context_middleware)
app.middleware("http")(security_headers_middleware)
cors_setup_middleware(app)
app.add_middleware(GZipMiddleware)

app.include_router(gocryptfs_init, prefix=config.API_PREFIX)

app.add_exception_handler(InternalServerError, internal_server_error_handler)
app.add_exception_handler(ResourceConflictError, resource_conflict_handler)
