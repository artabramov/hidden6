# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only


class InternalServerError(Exception):
    """Raised when an unexpected internal error occurs (500)."""
    pass


class ResourceNotFoundError(Exception):
    """Raised when the requested resource does not exist (404)."""
    pass


class ResourceConflictError(Exception):
    """Raised when the requested operation causes a conflict (409)."""
    pass
