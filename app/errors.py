# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only

# NOTE (ADR-09): API errors are status-only recovery classes.
# Exception handlers return an empty body. The HTTP status code is
# the entire public contract: one exception class maps to one status.
# Causes that share the same recovery raise the same exception.
# The only exception is the 422 response for basic Pydantic request
# validation. It preserves field-level validation details.


class InternalServerError(Exception):
    """Raised when an unexpected internal error occurs (500)."""
    pass


class UnauthorizedError(Exception):
    """Raised when credentials are invalid (401)."""
    pass


class ResourceConflictError(Exception):
    """Raised when the requested operation causes a conflict (409)."""
    pass


class ServiceUnavailableError(Exception):
    """Raised when the cipherdir or secrets are unavailable (503)."""
    pass
