# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only

# NOTE (ADR-09): API errors are status-only recovery classes.
# Exception handlers return an empty body. The HTTP status code is
# the entire public contract: one exception class maps to one status.
# Causes that share the same recovery raise the same exception.
# The only exception is the 422 response for basic Pydantic request
# validation. It preserves field-level validation details.
# 401 Unauthorized Error        — master password incorrect or stored
#                                 passphrase cannot be decrypted
# 409 Resource Conflict Error   — storage already or not yet connected
#                                 (mounted / unmounted), or init
#                                 conflicts with existing state/secrets
# 412 Precondition Failed Error — storage not initialized (cipherdir
#                                 missing); client should run init
# 422 Unprocessable Content     — request body failed schema validation
# 500 Internal Server Error     — unexpected failure
# 503 Service Unavailable Error — storage or passphrase unavailable
#                                 (e.g. passphrase missing after init);
#                                 do not blindly retry — check
#                                 volumes/health


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
    """
    Raised when storage or required secrets are unavailable (503).
    """
    pass
