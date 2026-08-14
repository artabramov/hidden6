# app/s3/validation.py
# SPDX-License-Identifier: GPL-3.0-only

import re

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.errors import S3InvalidBucketNameError, S3ObjektKeyInvalidError

# AWS S3 bucket naming (DNS-compliant). The pattern also carries the
# length limits, because a name is one leading character, up to 61 in
# the middle, and one trailing character.
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_IP_ADDRESS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

# Segments that cannot be mapped onto a filesystem path. Empty rejects
# an empty key, a leading or trailing slash, and repeated slashes.
_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})

# NOTE (ADR-24): S3 object keys map to nested filesystem paths.
# A key is stored as a path relative to the bucket directory, so the
# key photos/2024/cat.png becomes a file in nested directories that
# are created on upload. Because directories and files share one
# namespace on disk, a key colliding with a stored object is rejected
# instead of being flattened into a single filename.


def bucket_name_validate(
    bucket_name: str,
    resource: str,
) -> None:
    """
    Reject a bucket name that violates S3 DNS naming rules before it
    reaches storage, where the name becomes a directory of its own.

    Raises:
        S3InvalidBucketNameError: Name is not a valid bucket name.
    """
    if not _BUCKET_NAME_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)

    if ".." in bucket_name or ".-" in bucket_name or "-." in bucket_name:
        raise S3InvalidBucketNameError(resource)

    if _IP_ADDRESS_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)


def objekt_key_validate(object_key: str, resource: str) -> None:
    """
    Reject an object key that cannot be stored as a path relative to
    the bucket directory: oversized, holding a null byte, or carrying a
    segment that is empty, a dot, or a double dot.

    Raises:
        S3ObjektKeyInvalidError: Key is not a valid object key.
    """
    if len(object_key.encode("utf-8")) > OBJEKT_KEY_MAX_BYTES:
        raise S3ObjektKeyInvalidError(resource)

    if "\x00" in object_key:
        raise S3ObjektKeyInvalidError(resource)

    if any(part in _FORBIDDEN_SEGMENTS for part in object_key.split("/")):
        raise S3ObjektKeyInvalidError(resource)
