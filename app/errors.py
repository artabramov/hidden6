# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only

# NOTE (ADR-11): HTTP 401/502/503 are reserved for gocryptfs errors.
# 401 indicates master-password authentication failure. 502 indicates
# unexpected presence of cipherdir, mount, passphrase, or related
# secrets such as the Fernet encryption key. 503 indicates missing
# required gocryptfs infrastructure. All other application errors,
# including SigV4 authentication failures, use different status codes
# (for example, 403 Forbidden for SigV4).


class UnauthorizedError(Exception):
    """Raised when credentials are invalid (401)."""
    pass


class ForbiddenError(Exception):
    """Raised when SigV4 authentication or authorization fails (403)."""
    pass


class ResourceConflictError(Exception):
    """Raised when the requested operation causes a conflict (409)."""
    pass


class InternalServerError(Exception):
    """Raised when an unexpected internal error occurs (500)."""
    pass


class BadGatewayError(Exception):
    """Raised when gocryptfs infra is in a conflicting state (502)."""
    pass


class ServiceUnavailableError(Exception):
    """Raised when the cipherdir or secrets are unavailable (503)."""
    pass


class S3Error(Exception):
    """
    Raised for S3 API client errors returned as XML Error documents.
    Carries an S3 Error Code, message, HTTP status, and optional
    Resource path (for example AccessDenied, InvalidBucketName).
    """

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        resource: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.resource = resource
        super().__init__(code)
