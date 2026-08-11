# app/schemas/bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

from datetime import UTC, datetime
from xml.sax.saxutils import escape

from app.models.bucket import Bucket
from app.models.user import User

S3_XMLNS = "http://s3.amazonaws.com/doc/2006-03-01/"


def format_creation_date(unix_ts: int) -> str:
    """Format a bucket creation timestamp as S3 ISO 8601 UTC."""
    dt = datetime.fromtimestamp(unix_ts, tz=UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


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
                f"{format_creation_date(bucket.created_at)}"
                f"</CreationDate>"
            ),
            "</Bucket>",
        ])
    parts.extend([
        "</Buckets>",
        "</ListAllMyBucketsResult>",
    ])
    return "".join(parts)
