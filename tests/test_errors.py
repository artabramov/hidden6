# tests/test_errors.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from fastapi import status

from app.errors import (
    BadGatewayError,
    InternalServerError,
    S3AccessDeniedError,
    S3BucketAlreadyExistsError,
    S3BucketAlreadyOwnedByYouError,
    S3BucketNotFoundError,
    S3BucketStateInvalidError,
    S3Error,
    S3ErrorCode,
    S3IllegalVersioningConfigurationError,
    S3InvalidAccessKeyIdError,
    S3InvalidBucketNameError,
    S3NotImplementedError,
    S3ObjektBodyIncompleteError,
    S3ObjektKeyConflictError,
    S3ObjektKeyInvalidError,
    S3ObjektNotFoundError,
    S3ObjektPartInvalidError,
    S3ObjektPartNumberInvalidError,
    S3ObjektPartOrderInvalidError,
    S3ObjektPartTooSmallError,
    S3ObjektTooLargeError,
    S3ObjektUploadNotFoundError,
    S3ObjektXmlMalformedError,
    S3RequestTimeTooSkewedError,
    S3SignatureDoesNotMatchError,
    ServiceUnavailableError,
    UnauthorizedError,
)


class TestInternalErrors(unittest.TestCase):
    def test_are_plain_exceptions(self):
        for cls in (
            UnauthorizedError,
            InternalServerError,
            BadGatewayError,
            ServiceUnavailableError,
        ):
            with self.subTest(cls=cls.__name__):
                exc = cls()
                self.assertIsInstance(exc, Exception)
                self.assertFalse(isinstance(exc, S3Error))


class TestS3Error(unittest.TestCase):
    def test_stores_fields(self):
        exc = S3Error(
            code="AccessDenied",
            message="denied",
            status_code=403,
            resource="/photos",
        )

        self.assertEqual(exc.code, "AccessDenied")
        self.assertEqual(exc.message, "denied")
        self.assertEqual(exc.status_code, 403)
        self.assertEqual(exc.resource, "/photos")
        self.assertEqual(str(exc), "AccessDenied")

    def test_resource_defaults_to_none(self):
        exc = S3Error(
            code="AccessDenied",
            message="denied",
            status_code=403,
        )

        self.assertIsNone(exc.resource)


class TestS3ErrorSubclasses(unittest.TestCase):
    CASES = (
        (
            S3AccessDeniedError,
            S3ErrorCode.ACCESS_DENIED,
            status.HTTP_403_FORBIDDEN,
        ),
        (
            S3InvalidAccessKeyIdError,
            S3ErrorCode.INVALID_ACCESS_KEY_ID,
            status.HTTP_403_FORBIDDEN,
        ),
        (
            S3SignatureDoesNotMatchError,
            S3ErrorCode.SIGNATURE_DOES_NOT_MATCH,
            status.HTTP_403_FORBIDDEN,
        ),
        (
            S3RequestTimeTooSkewedError,
            S3ErrorCode.REQUEST_TIME_TOO_SKEWED,
            status.HTTP_403_FORBIDDEN,
        ),
        (
            S3InvalidBucketNameError,
            S3ErrorCode.BUCKET_NAME_INVALID,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3BucketAlreadyExistsError,
            S3ErrorCode.BUCKET_ALREADY_EXISTS,
            status.HTTP_409_CONFLICT,
        ),
        (
            S3BucketAlreadyOwnedByYouError,
            S3ErrorCode.BUCKET_ALREADY_OWNED_BY_YOU,
            status.HTTP_409_CONFLICT,
        ),
        (
            S3BucketNotFoundError,
            S3ErrorCode.BUCKET_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            S3BucketStateInvalidError,
            S3ErrorCode.BUCKET_STATE_INVALID,
            status.HTTP_409_CONFLICT,
        ),
        (
            S3ObjektNotFoundError,
            S3ErrorCode.OBJEKT_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            S3ObjektKeyInvalidError,
            S3ErrorCode.OBJEKT_KEY_INVALID,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektKeyConflictError,
            S3ErrorCode.OBJEKT_KEY_CONFLICT,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektTooLargeError,
            S3ErrorCode.OBJEKT_TOO_LARGE,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektBodyIncompleteError,
            S3ErrorCode.OBJEKT_BODY_INCOMPLETE,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektUploadNotFoundError,
            S3ErrorCode.OBJEKT_UPLOAD_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
        ),
        (
            S3ObjektPartNumberInvalidError,
            S3ErrorCode.OBJEKT_PART_NUMBER_INVALID,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektPartInvalidError,
            S3ErrorCode.OBJEKT_PART_INVALID,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektPartOrderInvalidError,
            S3ErrorCode.OBJEKT_PART_ORDER_INVALID,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektPartTooSmallError,
            S3ErrorCode.OBJEKT_PART_TOO_SMALL,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3ObjektXmlMalformedError,
            S3ErrorCode.OBJEKT_XML_MALFORMED,
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            S3NotImplementedError,
            S3ErrorCode.NOT_IMPLEMENTED,
            status.HTTP_501_NOT_IMPLEMENTED,
        ),
        (
            S3IllegalVersioningConfigurationError,
            S3ErrorCode.ILLEGAL_VERSIONING_CONFIGURATION,
            status.HTTP_400_BAD_REQUEST,
        ),
    )

    def test_sets_code_status_message_and_resource(self):
        for cls, code, status_code in self.CASES:
            with self.subTest(cls=cls.__name__):
                exc = cls("/photos/cat.png")

                self.assertIsInstance(exc, S3Error)
                self.assertEqual(exc.code, code)
                self.assertEqual(exc.status_code, status_code)
                self.assertEqual(exc.resource, "/photos/cat.png")
                self.assertTrue(exc.message)

    def test_resource_is_optional(self):
        for cls, _code, _status_code in self.CASES:
            with self.subTest(cls=cls.__name__):
                exc = cls()
                self.assertIsNone(exc.resource)
