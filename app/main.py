# app/main.py
# SPDX-License-Identifier: GPL-3.0-only

from contextlib import asynccontextmanager
from starlette.middleware.gzip import GZipMiddleware
from fastapi import FastAPI

from app.version import __version__
from app.constants import HIDDEN_TITLE
from app.config import get_config
from app.hooks import hooks
from app.log import init_logging

from app.errors import (
    InternalServerError,
    BadRequestError,
    ResourceNotFoundError,
    ResourceConflictError,
)

from app.handlers import (
    internal_server_error_handler,
    bad_request_handler,
    resource_not_found_handler,
    resource_conflict_handler,
)

from app.middleware.cors_setup import cors_setup_middleware
from app.middleware.request_context import request_context_middleware
from app.middleware.request_logging import request_logging_middleware
from app.middleware.security_headers import security_headers_middleware

from app.routers.gocryptfs_init import router as gocryptfs_init_router
from app.routers.gocryptfs_mount import router as gocryptfs_mount_router
from app.routers.gocryptfs_unmount import router as gocryptfs_unmount_router

config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logging()
    hooks.load_extensions()
    yield


app = FastAPI(
    title=HIDDEN_TITLE,
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

app.include_router(gocryptfs_init_router, prefix=config.API_PREFIX)
app.include_router(gocryptfs_mount_router, prefix=config.API_PREFIX)
app.include_router(gocryptfs_unmount_router, prefix=config.API_PREFIX)

app.add_exception_handler(InternalServerError, internal_server_error_handler)
app.add_exception_handler(BadRequestError, bad_request_handler)
app.add_exception_handler(ResourceNotFoundError, resource_not_found_handler)
app.add_exception_handler(ResourceConflictError, resource_conflict_handler)
