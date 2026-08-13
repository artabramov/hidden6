# app/s3/datetime_http.py
# SPDX-License-Identifier: GPL-3.0-only

from email.utils import formatdate


def datetime_http(unix_ts: int) -> str:
    """
    Format a timestamp the way S3 carries time in HTTP headers:
    RFC 1123 / IMF-fixdate in GMT (for example Last-Modified).
    """
    return formatdate(unix_ts, usegmt=True)
