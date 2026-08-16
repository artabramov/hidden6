# app/s3/datetime.py
# SPDX-License-Identifier: GPL-3.0-only

from datetime import UTC, datetime
from email.utils import formatdate


def format_datetime(unix_ts: int) -> str:
    """
    Format a timestamp the way S3 carries time in XML bodies: ISO 8601
    in UTC with milliseconds and a Z suffix. Milliseconds are always
    zero because timestamps are stored with second precision, which is
    the precision S3 itself reports.
    """
    dt = datetime.fromtimestamp(unix_ts, tz=UTC)

    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def http_datetime(unix_ts: int) -> str:
    """
    Format a timestamp the way S3 carries time in HTTP headers:
    RFC 1123 / IMF-fixdate in GMT (for example Last-Modified).
    """
    return formatdate(unix_ts, usegmt=True)
