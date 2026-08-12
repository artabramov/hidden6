# app/validators/object_key.py
# SPDX-License-Identifier: GPL-3.0-only

from app.constants import OBJEKT_KEY_MAX_BYTES

# Segments that cannot be mapped onto a filesystem path. Empty rejects
# an empty key, a leading or trailing slash, and repeated slashes.
_FORBIDDEN_SEGMENTS = frozenset({"", ".", ".."})


def validate_object_key(value: str) -> str:
    """
    Validate an S3 object key. Returns the key unchanged when valid.

    Raises:
        ValueError: Key is empty, too long, or cannot be stored as a
        path relative to the bucket directory.
    """
    if len(value.encode("utf-8")) > OBJEKT_KEY_MAX_BYTES:
        raise ValueError("Invalid object key.")
    if "\x00" in value:
        raise ValueError("Invalid object key.")
    if any(part in _FORBIDDEN_SEGMENTS for part in value.split("/")):
        raise ValueError("Invalid object key.")
    return value
