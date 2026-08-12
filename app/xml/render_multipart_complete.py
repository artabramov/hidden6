# app/xml/render_multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from app.constants import S3_XMLNS


def render_multipart_complete(
    bucket_name: str,
    object_key: str,
    etag: str,
) -> str:
    """
    Render an S3-compatible XML response for CompleteMultipartUpload,
    carrying the location and the ETag of the assembled object.
    """
    location = f"/{bucket_name}/{object_key}"
    quoted_etag = f'"{etag}"'

    return "".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<CompleteMultipartUploadResult xmlns="{S3_XMLNS}">',
        f"<Location>{escape(location)}</Location>",
        f"<Bucket>{escape(bucket_name)}</Bucket>",
        f"<Key>{escape(object_key)}</Key>",
        f"<ETag>{escape(quoted_etag)}</ETag>",
        "</CompleteMultipartUploadResult>",
    ])
