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
    UnauthorizedError,
    InternalServerError,
    BadGatewayError,
    ServiceUnavailableError,
    S3Error,
)

from app.handlers import (
    internal_server_error_handler,
    unauthorized_handler,
    service_unavailable_handler,
    bad_gateway_handler,
    s3_error_handler,
)

from app.middleware.cors_setup import cors_setup_middleware
from app.middleware.request_context import request_context_middleware
from app.middleware.request_logging import request_logging_middleware
from app.middleware.security_headers import security_headers_middleware

from app.routers.gocryptfs_init import router as gocryptfs_init_router
from app.routers.gocryptfs_mount import router as gocryptfs_mount_router
from app.routers.gocryptfs_unmount import router as gocryptfs_unmount_router
from app.routers.gocryptfs_rotate import router as gocryptfs_rotate_router
from app.routers.gocryptfs_reveal import router as gocryptfs_reveal_router
from app.routers.gocryptfs_health import router as gocryptfs_health_router
from app.routers.user_init import router as user_init_router
from app.routers.bucket_create import router as bucket_create_router
from app.routers.bucket_list import router as bucket_list_router
from app.routers.objekt_upload import router as objekt_upload_router
from app.routers.objekt_multipart import router as objekt_multipart_router

config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_logging()
    from app.db.engine import load_all_models  # noqa: PLC0415
    load_all_models()
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

# NOTE (ADR-06): Application middleware execution order is fixed.
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

# NOTE (ADR-22): S3 routes are excluded from the OpenAPI schema.
# S3 requests require AWS Signature Version 4, which Swagger UI does
# not support. S3 operations are therefore performed through AWS CLI
# or another S3-compatible client against the application root.

app.include_router(gocryptfs_init_router, prefix=config.API_PREFIX)
app.include_router(gocryptfs_mount_router, prefix=config.API_PREFIX)
app.include_router(gocryptfs_unmount_router, prefix=config.API_PREFIX)
app.include_router(gocryptfs_rotate_router, prefix=config.API_PREFIX)
app.include_router(gocryptfs_reveal_router, prefix=config.API_PREFIX)
app.include_router(gocryptfs_health_router, prefix=config.API_PREFIX)
app.include_router(user_init_router, prefix=config.API_PREFIX)
app.include_router(bucket_list_router)
app.include_router(bucket_create_router)
app.include_router(objekt_upload_router)
app.include_router(objekt_multipart_router)

app.add_exception_handler(UnauthorizedError, unauthorized_handler)
app.add_exception_handler(InternalServerError, internal_server_error_handler)
app.add_exception_handler(BadGatewayError, bad_gateway_handler)
app.add_exception_handler(ServiceUnavailableError, service_unavailable_handler)
app.add_exception_handler(S3Error, s3_error_handler)
