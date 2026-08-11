# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import status

# NOTE (ADR-11): HTTP 401/502/503 are reserved for gocryptfs errors.
# 401 indicates master-password authentication failure. 502 indicates
# unexpected presence of cipherdir, mount, passphrase, or related
# secrets such as the Fernet encryption key. 503 indicates missing
# required gocryptfs infrastructure. S3 client errors use S3Error.


class S3ErrorCode:
    """S3 error codes returned in XML Error responses."""

    ACCESS_DENIED = "AccessDenied"


class UnauthorizedError(Exception):
    """Raised when credentials are invalid (401)."""
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


class S3AccessDeniedError(S3Error):
    """Raised when S3 access is denied (403)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.ACCESS_DENIED,
            message="Access Denied",
            status_code=status.HTTP_403_FORBIDDEN,
            resource=resource,
        )
