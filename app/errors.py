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
    NOT_IMPLEMENTED = "NotImplemented"

    XML_MALFORMED = "MalformedXML"

    BUCKET_NAME_INVALID = "InvalidBucketName"
    BUCKET_ALREADY_EXISTS = "BucketAlreadyExists"
    BUCKET_ALREADY_OWNED_BY_YOU = "BucketAlreadyOwnedByYou"
    BUCKET_NOT_FOUND = "NoSuchBucket"
    BUCKET_STATE_INVALID = "InvalidBucketState"
    ILLEGAL_VERSIONING_CONFIGURATION = "IllegalVersioningConfigurationException"  # noqa: E501

    OBJEKT_NOT_FOUND = "NoSuchKey"
    OBJEKT_KEY_INVALID = "InvalidArgument"
    OBJEKT_KEY_CONFLICT = "InvalidArgument"
    OBJEKT_TOO_LARGE = "EntityTooLarge"
    OBJEKT_BODY_INCOMPLETE = "IncompleteBody"
    OBJEKT_UPLOAD_NOT_FOUND = "NoSuchUpload"
    OBJEKT_PART_NUMBER_INVALID = "InvalidArgument"
    OBJEKT_PART_INVALID = "InvalidPart"
    OBJEKT_PART_ORDER_INVALID = "InvalidPartOrder"
    OBJEKT_PART_TOO_SMALL = "EntityTooSmall"


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


class S3InvalidBucketNameError(S3Error):
    """Raised when the bucket name is invalid (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.BUCKET_NAME_INVALID,
            message="The specified bucket is not valid.",
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3BucketAlreadyExistsError(S3Error):
    """Raised when the bucket name is taken by another owner (409)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.BUCKET_ALREADY_EXISTS,
            message=(
                "The requested bucket name is not available. The "
                "bucket namespace is shared by all users of the system."
            ),
            status_code=status.HTTP_409_CONFLICT,
            resource=resource,
        )


class S3BucketAlreadyOwnedByYouError(S3Error):
    """Raised when the caller already owns the bucket (409)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.BUCKET_ALREADY_OWNED_BY_YOU,
            message=(
                "The bucket already exists and is owned by the "
                "current user."
            ),
            status_code=status.HTTP_409_CONFLICT,
            resource=resource,
        )


class S3BucketNotFoundError(S3Error):
    """Raised when the bucket does not exist (404)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.BUCKET_NOT_FOUND,
            message="The specified bucket does not exist.",
            status_code=status.HTTP_404_NOT_FOUND,
            resource=resource,
        )


class S3BucketStateInvalidError(S3Error):
    """Raised when an operation is invalid for the bucket state (409)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.BUCKET_STATE_INVALID,
            message=(
                "The request is not valid for the current state of the "
                "bucket."
            ),
            status_code=status.HTTP_409_CONFLICT,
            resource=resource,
        )


class S3IllegalVersioningConfigurationError(S3Error):
    """Raised when the bucket versioning configuration is invalid (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.ILLEGAL_VERSIONING_CONFIGURATION,
            message=(
                "The versioning configuration specified in the request "
                "is not valid."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektNotFoundError(S3Error):
    """Raised when the object does not exist (404)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_NOT_FOUND,
            message="The specified key does not exist.",
            status_code=status.HTTP_404_NOT_FOUND,
            resource=resource,
        )


class S3ObjektKeyInvalidError(S3Error):
    """Raised when the object key is not a valid S3 key (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_KEY_INVALID,
            message="The specified object key is not valid.",
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektKeyConflictError(S3Error):
    """Raised when the key collides with a stored object (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_KEY_CONFLICT,
            message=(
                "The specified object key conflicts with an object "
                "already stored in the bucket."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektTooLargeError(S3Error):
    """Raised when the object exceeds the upload size limit (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_TOO_LARGE,
            message=(
                "The uploaded object exceeds the maximum size "
                "allowed by a single upload request."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektBodyIncompleteError(S3Error):
    """Raised when the uploaded body ends or frames wrongly (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_BODY_INCOMPLETE,
            message=(
                "The request body is incomplete or does not match "
                "the chunked encoding declared by the client."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektUploadNotFoundError(S3Error):
    """Raised when the multipart upload is unknown (404)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_UPLOAD_NOT_FOUND,
            message=(
                "The specified multipart upload does not exist. It "
                "may have been completed or aborted."
            ),
            status_code=status.HTTP_404_NOT_FOUND,
            resource=resource,
        )


class S3ObjektPartNumberInvalidError(S3Error):
    """Raised when the part number is out of the allowed range."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_PART_NUMBER_INVALID,
            message=(
                "The part number must be an integer between 1 and "
                "10000, inclusive."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektPartInvalidError(S3Error):
    """Raised when a listed part is missing or mismatched (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_PART_INVALID,
            message=(
                "One or more of the listed parts could not be found, "
                "or its entity tag does not match the uploaded part."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektPartOrderInvalidError(S3Error):
    """Raised when listed parts are not in ascending order (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_PART_ORDER_INVALID,
            message=(
                "The list of parts was not in ascending order. Parts "
                "must be ordered by part number."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3ObjektPartTooSmallError(S3Error):
    """Raised when a part other than the last is too small (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.OBJEKT_PART_TOO_SMALL,
            message=(
                "Each part but the last one must be at least 5 MiB "
                "in size."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3XmlMalformedError(S3Error):
    """Raised when the request XML cannot be parsed (400)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.XML_MALFORMED,
            message=(
                "The XML provided was not well formed or did not "
                "validate against the published schema."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
            resource=resource,
        )


class S3NotImplementedError(S3Error):
    """Raised when the requested S3 operation is missing (501)."""

    def __init__(self, resource: str | None = None) -> None:
        super().__init__(
            code=S3ErrorCode.NOT_IMPLEMENTED,
            message=(
                "The requested S3 operation is not implemented by "
                "this server."
            ),
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            resource=resource,
        )
