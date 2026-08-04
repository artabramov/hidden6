# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only

class InternalServerError(Exception):
    """Raised when an unexpected internal error occurs (500)."""
    pass


class ServiceUnavailableError(Exception):
    """Raised when the service is temporarily unavailable (503)."""
    pass


class ResourceNotFoundError(Exception):
    """Resource with given ID does not exist (404)."""
    pass


class ResourceForbiddenError(Exception):
    """Access to the requested resource is forbidden (403)."""
    pass


class ResourceConflictError(Exception):
    """Operation conflicts with current resource state (409)."""
    pass


class ResourceLockedError(Exception):
    """The resource that is being accessed is locked (423)."""
    pass


class TooManyRequestsError(Exception):
    """Raised when request rate exceeds allowed limits (429)."""
    pass
