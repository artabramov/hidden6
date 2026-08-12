# app/schemas/multipart_create.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from app.constants import S3_XMLNS


def render_initiate_multipart_xml(
    bucket_name: str,
    object_key: str,
    upload_id: str,
) -> str:
    """
    Render an S3-compatible XML response for CreateMultipartUpload,
    carrying the upload id the client sends back with every part.
    """
    return "".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<InitiateMultipartUploadResult xmlns="{S3_XMLNS}">',
        f"<Bucket>{escape(bucket_name)}</Bucket>",
        f"<Key>{escape(object_key)}</Key>",
        f"<UploadId>{escape(upload_id)}</UploadId>",
        "</InitiateMultipartUploadResult>",
    ])
