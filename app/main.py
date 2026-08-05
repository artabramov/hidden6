# app/main.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import FastAPI

from app.errors import (
    InternalServerError,
    ResourceConflictError,
)
from app.handlers import (
    internal_server_error_handler,
    resource_conflict_handler,
)
from app.routers.gocryptfs_initialize import router as initialize_gocryptfs

app = FastAPI(
    swagger_ui_parameters={
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "tryItOutEnabled": True,
    }
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


app.include_router(initialize_gocryptfs, prefix="/api/v1")

app.add_exception_handler(InternalServerError, internal_server_error_handler)
app.add_exception_handler(ResourceConflictError, resource_conflict_handler)
