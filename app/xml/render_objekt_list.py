# app/xml/render_objekt_list.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from app.constants import S3_XMLNS
from app.models.objekt import Objekt
from app.s3.datetime import datetime_format


def render_objekt_list(
    bucket_name: str,
    prefix: str,
    max_keys: int,
    objekts: list[Objekt],
) -> str:
    """
    Render an S3-compatible ListBucketResult XML body.

    IsTruncated is true when the number of returned objects equals
    max_keys, meaning further pages may exist; the client is expected
    to re-request with a continuation token (not yet implemented).
    """
    is_truncated = len(objekts) == max_keys
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<ListBucketResult xmlns="{S3_XMLNS}">',
        f"<Name>{escape(bucket_name)}</Name>",
        f"<Prefix>{escape(prefix)}</Prefix>",
        f"<MaxKeys>{max_keys}</MaxKeys>",
        f"<KeyCount>{len(objekts)}</KeyCount>",
        f"<IsTruncated>{'true' if is_truncated else 'false'}</IsTruncated>",
    ]
    for objekt in objekts:
        last_modified = datetime_format(objekt.modified_at)
        parts.extend([
            "<Contents>",
            f"<Key>{escape(objekt.object_key)}</Key>",
            f"<LastModified>{last_modified}</LastModified>",
            f"<ETag>&quot;{escape(objekt.etag)}&quot;</ETag>",
            f"<Size>{objekt.size_bytes}</Size>",
            "<StorageClass>STANDARD</StorageClass>",
            "</Contents>",
        ])
    parts.append("</ListBucketResult>")
    return "".join(parts)
