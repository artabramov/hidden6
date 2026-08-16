# app/s3/headers.py
# SPDX-License-Identifier: GPL-3.0-only

from app.models.objekt import Objekt
from app.s3.datetime import http_datetime


def objekt_headers(objekt: Objekt) -> dict[str, str]:
    """
    Response headers shared by GetObject and HeadObject.
    """
    return {
        "Content-Length": str(objekt.size_bytes),
        "ETag": f'"{objekt.etag}"',
        "Last-Modified": http_datetime(objekt.modified_at),
    }
