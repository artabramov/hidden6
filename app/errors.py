# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only


class InternalServerError(Exception):
    """Raised when an unexpected internal error occurs (500)."""
    pass


class ResourceConflictError(Exception):
    """Operation conflicts with current resource state (409)."""
    pass
