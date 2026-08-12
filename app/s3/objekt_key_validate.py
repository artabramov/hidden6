# app/s3/objekt_key_validate.py
# SPDX-License-Identifier: GPL-3.0-only

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.errors import S3ObjektKeyInvalidError

# Segments that cannot be mapped onto a filesystem path. Empty rejects
# an empty key, a leading or trailing slash, and repeated slashes.
_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})


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
