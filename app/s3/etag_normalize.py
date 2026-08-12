# app/s3/etag_normalize.py
# SPDX-License-Identifier: GPL-3.0-only


def etag_normalize(value: str) -> str:
    """
    Reduce an ETag to the bare hash it stands for. S3 carries ETags
    wrapped in quotes on the wire, and clients echo them back with the
    quotes kept, dropped, or upper-cased, so a listed part matches a
    stored one only after the quoting is stripped away.
    """
    return value.strip().strip('"').lower()
