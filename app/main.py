# app/main.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import FastAPI

from app.config import get_config

from app.errors import (
    InternalServerError,
    ResourceConflictError,
)

from app.handlers import (
    internal_server_error_handler,
    resource_conflict_handler,
)

from app.routers.gocryptfs_initialize import router as initialize_gocryptfs

config = get_config()

app = FastAPI(
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    }
)

app.include_router(initialize_gocryptfs, prefix=config.API_PREFIX)

app.add_exception_handler(InternalServerError, internal_server_error_handler)
app.add_exception_handler(ResourceConflictError, resource_conflict_handler)
