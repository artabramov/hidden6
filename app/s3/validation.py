# app/s3/validation.py
# SPDX-License-Identifier: GPL-3.0-only

import re

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.errors import S3InvalidBucketNameError, S3ObjektKeyInvalidError

# General-purpose S3 bucket name syntax, including the 3–63 character
# length limit and the requirement for alphanumeric boundary characters.
_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")

# IPv4-like names are reserved and cannot be used as S3 bucket names.
_IP_ADDRESS_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

# Prefixes and suffixes reserved by S3 for other bucket or access
# point namespaces.
_BUCKET_RESERVED_PREFIXES = (
    "xn--",
    "sthree-",
    "amzn-s3-demo-",
)

_BUCKET_RESERVED_SUFFIXES = (
    "-s3alias",
    "--ol-s3",
    ".mrap",
    "--x-s3",
    "--table-s3",
)

# Path segments that cannot be represented safely by the filesystem
# mapping. An empty segment also rejects empty keys, leading or trailing
# slashes, and repeated slashes.
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
    Validate a general-purpose S3 bucket name.

    Enforces the S3 naming syntax, reserved namespace restrictions,
    and names that resemble IPv4 addresses before the bucket name is
    used as a storage directory.

    Raises:
        S3InvalidBucketNameError: Bucket name violates S3 naming rules.
    """
    if not _BUCKET_NAME_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)

    if ".." in bucket_name or ".-" in bucket_name or "-." in bucket_name:
        raise S3InvalidBucketNameError(resource)

    if _IP_ADDRESS_RE.fullmatch(bucket_name):
        raise S3InvalidBucketNameError(resource)

    if bucket_name.startswith(_BUCKET_RESERVED_PREFIXES):
        raise S3InvalidBucketNameError(resource)

    if bucket_name.endswith(_BUCKET_RESERVED_SUFFIXES):
        raise S3InvalidBucketNameError(resource)


def objekt_key_validate(object_key: str, resource: str) -> None:
    """
    Validate an S3 object key for the filesystem-backed namespace.

    The key must fit within the S3 UTF-8 byte limit and must not contain
    null bytes or path segments that cannot be mapped safely to the
    filesystem. This intentionally makes the accepted key namespace
    narrower than S3 itself.

    Raises:
        S3ObjektKeyInvalidError: Object key cannot be represented safely.
    """
    try:
        object_key_bytes = object_key.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise S3ObjektKeyInvalidError(resource) from exc

    if len(object_key_bytes) > OBJEKT_KEY_MAX_BYTES:
        raise S3ObjektKeyInvalidError(resource)

    if "\x00" in object_key:
        raise S3ObjektKeyInvalidError(resource)

    if any(part in _FORBIDDEN_SEGMENTS for part in object_key.split("/")):
        raise S3ObjektKeyInvalidError(resource)
