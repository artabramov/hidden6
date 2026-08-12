# app/xml/bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from app.constants import S3_XMLNS
from app.models.bucket import Bucket
from app.models.user import User
from app.s3.datetime_format import datetime_format


def render_list_buckets_xml(
    owner: User,
    buckets: list[Bucket],
) -> str:
    """
    Render an S3-compatible XML response containing the bucket list.
    Includes the response owner and creation timestamp for each bucket.
    """
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<ListAllMyBucketsResult xmlns="{S3_XMLNS}">',
        "<Owner>",
        f"<ID>{escape(str(owner.id))}</ID>",
        f"<DisplayName>{escape(owner.username)}</DisplayName>",
        "</Owner>",
        "<Buckets>",
    ]
    for bucket in buckets:
        parts.extend([
            "<Bucket>",
            f"<Name>{escape(bucket.bucket_name)}</Name>",
            (
                f"<CreationDate>"
                f"{datetime_format(bucket.created_at)}"
                f"</CreationDate>"
            ),
            "</Bucket>",
        ])
    parts.extend([
        "</Buckets>",
        "</ListAllMyBucketsResult>",
    ])
    return "".join(parts)
