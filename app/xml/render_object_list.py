# app/xml/render_object_list.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from app.constants import S3_XMLNS
from app.models.object import S3Object
from app.s3.datetime import format_datetime


def render_object_list(
    bucket_name: str,
    prefix: str,
    max_keys: int,
    s3_objects: list[S3Object],
) -> str:
    """
    Render an S3-compatible ListBucketResult XML body.

    IsTruncated is true when the number of returned objects equals
    max_keys, meaning further pages may exist; the client is expected
    to re-request with a continuation token (not yet implemented).
    """
    is_truncated = len(s3_objects) == max_keys
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<ListBucketResult xmlns="{S3_XMLNS}">',
        f"<Name>{escape(bucket_name)}</Name>",
        f"<Prefix>{escape(prefix)}</Prefix>",
        f"<MaxKeys>{max_keys}</MaxKeys>",
        f"<KeyCount>{len(s3_objects)}</KeyCount>",
        f"<IsTruncated>{'true' if is_truncated else 'false'}</IsTruncated>",
    ]
    for s3_object in s3_objects:
        last_modified = format_datetime(s3_object.modified_at)
        parts.extend([
            "<Contents>",
            f"<Key>{escape(s3_object.object_key)}</Key>",
            f"<LastModified>{last_modified}</LastModified>",
            f"<ETag>&quot;{escape(s3_object.etag)}&quot;</ETag>",
            f"<Size>{s3_object.size_bytes}</Size>",
            "<StorageClass>STANDARD</StorageClass>",
            "</Contents>",
        ])
    parts.append("</ListBucketResult>")
    return "".join(parts)
