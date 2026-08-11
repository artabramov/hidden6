# app/errors.py
# SPDX-License-Identifier: GPL-3.0-only

from fastapi import status

# NOTE (ADR-11): HTTP 401/502/503 are reserved for internal errors.
# 401 indicates master-password authentication failure. 502 indicates
# unexpected presence of cipherdir, mount, passphrase, related secrets,
# or other internal infrastructure conflicts. 503 indicates missing
# required gocryptfs infrastructure. S3 client errors use S3-based
# custom errors.


class UnauthorizedError(Exception):
    """Raised when credentials are invalid (401)."""
    pass


class InternalServerError(Exception):
    """Raised when an unexpected internal error occurs (500)."""
    pass


class BadGatewayError(Exception):
    """Raised when infrastructure is in a conflicting state (502)."""
    pass


class ServiceUnavailableError(Exception):
    """Raised when the cipherdir or secrets are unavailable (503)."""
    pass


class S3ErrorCode:
    """S3 error codes returned in XML Error responses."""

    ACCESS_DENIED = "AccessDenied"
    INVALID_ACCESS_KEY_ID = "InvalidAccessKeyId"
    SIGNATURE_DOES_NOT_MATCH = "SignatureDoesNotMatch"
    REQUEST_TIME_TOO_SKEWED = "RequestTimeTooSkewed"


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
            message="Access to the requested resource is denied.",
            status_code=status.HTTP_403_FORBIDDEN,
            resource=resource,
        )


class S3InvalidAccessKeyIdError(S3Error):
    """Raised when the access key id is unknown (403)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.INVALID_ACCESS_KEY_ID,
            message="The provided access key ID does not exist.",
            status_code=status.HTTP_403_FORBIDDEN,
            resource=resource,
        )


class S3SignatureDoesNotMatchError(S3Error):
    """Raised when the request signature is invalid (403)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.SIGNATURE_DOES_NOT_MATCH,
            message=(
                "The calculated request signature does not match "
                "the provided signature."
            ),
            status_code=status.HTTP_403_FORBIDDEN,
            resource=resource,
        )


class S3RequestTimeTooSkewedError(S3Error):
    """Raised when the request timestamp is outside the allowed skew."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.REQUEST_TIME_TOO_SKEWED,
            message=(
                "The difference between the request time and the "
                "current time is too large."
            ),
            status_code=status.HTTP_403_FORBIDDEN,
            resource=resource,
        )
