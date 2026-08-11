# app/validators/bucket_name.py
# SPDX-License-Identifier: GPL-3.0-only

import re

# AWS S3 bucket naming (DNS-compliant), length matches bucket_name.
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_IP_ADDRESS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def validate_bucket_name(value: str) -> str:
    """
    Validate an S3 bucket name. Returns the name unchanged when valid.

    Raises:
        ValueError: Name violates AWS S3 naming rules.
    """
    if not _BUCKET_NAME_RE.fullmatch(value):
        raise ValueError("Invalid bucket name.")
    if ".." in value or ".-" in value or "-." in value:
        raise ValueError("Invalid bucket name.")
    if _IP_ADDRESS_RE.fullmatch(value):
        raise ValueError("Invalid bucket name.")
    return value
