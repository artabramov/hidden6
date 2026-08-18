# app/s3/headers.py
# SPDX-License-Identifier: GPL-3.0-only

from app.models.object import Objekt
from app.s3.datetime import http_datetime


def etag_headers(etag: str) -> dict[str, str]:
    """
    ETag response header for PutObject and UploadPart.
    """
    return {"ETag": f'"{etag}"'}


def object_headers(objekt: Objekt) -> dict[str, str]:
    """
    Response headers shared by GetObject and HeadObject.
    """
    return {
        "Content-Length": str(objekt.size_bytes),
        **etag_headers(objekt.etag),
        "Last-Modified": http_datetime(objekt.modified_at),
    }
