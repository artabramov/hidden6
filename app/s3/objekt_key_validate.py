# app/s3/objekt_key_validate.py
# SPDX-License-Identifier: GPL-3.0-only

from app.errors import S3ObjektKeyInvalidError
from app.validators.object_key import validate_object_key


def objekt_key_validate(object_key: str, resource: str) -> None:
    """
    Reject an object key that cannot be stored as a path relative to
    the bucket directory: empty, oversized, holding a null byte, or
    carrying a segment that is empty, a dot, or a double dot.

    Raises:
        S3ObjektKeyInvalidError: Key is not a valid object key.
    """
    try:
        validate_object_key(object_key)
    except ValueError as exc:
        raise S3ObjektKeyInvalidError(resource) from exc
