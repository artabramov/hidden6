# tests/security/test_sigv4.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import hmac
import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from starlette.requests import Request

from app.errors import S3AccessDeniedError
from app.security import sigv4
from app.security.sigv4 import (
    ALGORITHM,
    EMPTY_PAYLOAD_HASH,
    UNSIGNED_PAYLOAD,
    extract_sigv4_auth,
    resolve_payload_hash,
    uri_encode,
    verify_sigv4,
)


ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
REGION = "us-east-1"
SERVICE = "s3"


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    key = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    key = _hmac(key, region)
    key = _hmac(key, service)
    return _hmac(key, "aws4_request")


def _sign_headers(
    *,
    method: str,
    path: str,
    query: list[tuple[str, str]] | None = None,
    headers: dict[str, str],
    payload: bytes,
    amz_date: str,
    secret: str = SECRET_KEY,
    region: str = REGION,
    service: str = SERVICE,
    access_key: str = ACCESS_KEY,
    unsigned_payload: bool = False,
) -> dict[str, str]:
    query = query or []
    datestamp = amz_date[:8]
    payload_hash = (
        UNSIGNED_PAYLOAD
        if unsigned_payload
        else hashlib.sha256(payload).hexdigest()
    )
    headers = {
        **headers,
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
    }
    signed_header_names = tuple(sorted(name.lower() for name in headers))
    canonical_headers = "".join(
        f"{name}:{sigv4._canonicalize_header_value(headers[name])}\n"
        for name in signed_header_names
    )
    canonical_query = _canonical_query(query)

    canonical_request = "\n".join((
        method.upper(),
        sigv4._canonical_uri(path),
        canonical_query,
        canonical_headers,
        ";".join(signed_header_names),
        payload_hash,
    ))
    scope = f"{datestamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join((
        ALGORITHM,
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ))
    signature = hmac.new(
        _signing_key(secret, datestamp, region, service),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    credential = f"{access_key}/{scope}"
    headers["authorization"] = (
        f"{ALGORITHM} Credential={credential}, "
        f"SignedHeaders={';'.join(signed_header_names)}, "
        f"Signature={signature}"
    )
    return headers


def _canonical_query(pairs: list[tuple[str, str]]) -> str:
    encoded = [
        (uri_encode(k, encode_slash=True), uri_encode(v, encode_slash=True))
        for k, v in pairs
    ]
    encoded.sort(key=lambda item: (item[0], item[1]))
    return "&".join(f"{k}={v}" for k, v in encoded)


def _make_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    query: list[tuple[str, str]] | None = None,
    body: bytes = b"",
) -> Request:
    query = query or []
    query_string = urlencode(query, doseq=True).encode("utf-8")
    header_list = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": query_string,
        "headers": header_list,
        "client": ("127.0.0.1", 123),
        "server": ("testserver", 80),
    }

    async def receive() -> dict:
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    return Request(scope, receive)


class TestUriEncode(unittest.TestCase):
    def test_leaves_unreserved_and_optionally_slash(self):
        self.assertEqual(uri_encode("abc-._~"), "abc-._~")
        self.assertEqual(uri_encode("a/b", encode_slash=False), "a/b")
        self.assertEqual(uri_encode("a/b", encode_slash=True), "a%2Fb")
        self.assertEqual(uri_encode("a b"), "a%20b")


class TestExtractAndVerify(unittest.IsolatedAsyncioTestCase):
    async def test_header_auth_roundtrip(self):
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        body = b"hello"
        headers = _sign_headers(
            method="PUT",
            path="/bucket/object",
            headers={"host": "localhost", "content-type": "text/plain"},
            payload=body,
            amz_date=amz_date,
        )
        request = _make_request(
            "PUT",
            "/bucket/object",
            headers=headers,
            body=body,
        )

        auth = extract_sigv4_auth(request)
        payload_hash = await resolve_payload_hash(request)
        verify_sigv4(
            request,
            auth,
            SECRET_KEY,
            expected_region=REGION,
            expected_service=SERVICE,
            max_skew_seconds=900,
            payload_hash=payload_hash,
        )

        self.assertEqual(auth.access_key_id, ACCESS_KEY)
        self.assertEqual(auth.source, "header")
        self.assertEqual(payload_hash, hashlib.sha256(body).hexdigest())

    async def test_unsigned_payload(self):
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = _sign_headers(
            method="GET",
            path="/bucket",
            headers={"host": "localhost"},
            payload=b"",
            amz_date=amz_date,
            unsigned_payload=True,
        )
        request = _make_request("GET", "/bucket", headers=headers)

        auth = extract_sigv4_auth(request)
        payload_hash = await resolve_payload_hash(request)
        verify_sigv4(
            request,
            auth,
            SECRET_KEY,
            expected_region=REGION,
            expected_service=SERVICE,
            max_skew_seconds=900,
            payload_hash=payload_hash,
        )
        self.assertEqual(payload_hash, UNSIGNED_PAYLOAD)

    async def test_rejects_bad_signature(self):
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = _sign_headers(
            method="GET",
            path="/bucket",
            headers={"host": "localhost"},
            payload=b"",
            amz_date=amz_date,
        )
        headers["authorization"] = headers["authorization"][:-4] + "dead"
        request = _make_request("GET", "/bucket", headers=headers)

        auth = extract_sigv4_auth(request)
        with self.assertRaises(S3AccessDeniedError):
            verify_sigv4(
                request,
                auth,
                SECRET_KEY,
                expected_region=REGION,
                expected_service=SERVICE,
                max_skew_seconds=900,
                payload_hash=EMPTY_PAYLOAD_HASH,
            )

    async def test_rejects_missing_auth(self):
        request = _make_request(
            "GET",
            "/bucket",
            headers={"host": "localhost"},
        )
        with self.assertRaises(S3AccessDeniedError):
            extract_sigv4_auth(request)

    async def test_rejects_clock_skew(self):
        skewed = datetime.now(timezone.utc) - timedelta(hours=1)
        amz_date = skewed.strftime("%Y%m%dT%H%M%SZ")
        headers = _sign_headers(
            method="GET",
            path="/bucket",
            headers={"host": "localhost"},
            payload=b"",
            amz_date=amz_date,
        )
        request = _make_request("GET", "/bucket", headers=headers)

        auth = extract_sigv4_auth(request)
        with self.assertRaises(S3AccessDeniedError):
            verify_sigv4(
                request,
                auth,
                SECRET_KEY,
                expected_region=REGION,
                expected_service=SERVICE,
                max_skew_seconds=900,
                payload_hash=EMPTY_PAYLOAD_HASH,
            )

    async def test_rejects_wrong_region(self):
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = _sign_headers(
            method="GET",
            path="/bucket",
            headers={"host": "localhost"},
            payload=b"",
            amz_date=amz_date,
            region="eu-west-1",
        )
        request = _make_request("GET", "/bucket", headers=headers)

        auth = extract_sigv4_auth(request)
        with self.assertRaises(S3AccessDeniedError):
            verify_sigv4(
                request,
                auth,
                SECRET_KEY,
                expected_region=REGION,
                expected_service=SERVICE,
                max_skew_seconds=900,
                payload_hash=EMPTY_PAYLOAD_HASH,
            )

    async def test_rejects_payload_hash_mismatch(self):
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        headers = _sign_headers(
            method="PUT",
            path="/bucket/object",
            headers={"host": "localhost"},
            payload=b"signed-body",
            amz_date=amz_date,
        )
        request = _make_request(
            "PUT",
            "/bucket/object",
            headers=headers,
            body=b"tampered-body",
        )
        with self.assertRaises(S3AccessDeniedError):
            await resolve_payload_hash(request)

    async def test_query_auth_roundtrip(self):
        amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        datestamp = amz_date[:8]
        expires = 900
        path = "/bucket/object"
        scope = f"{datestamp}/{REGION}/{SERVICE}/aws4_request"
        credential = f"{ACCESS_KEY}/{scope}"
        signed_headers = ("host",)
        query = [
            ("X-Amz-Algorithm", ALGORITHM),
            ("X-Amz-Credential", credential),
            ("X-Amz-Date", amz_date),
            ("X-Amz-Expires", str(expires)),
            ("X-Amz-SignedHeaders", "host"),
        ]
        canonical_query = _canonical_query(query)
        canonical_request = "\n".join((
            "GET",
            path,
            canonical_query,
            "host:localhost\n",
            "host",
            UNSIGNED_PAYLOAD,
        ))
        string_to_sign = "\n".join((
            ALGORITHM,
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ))
        signature = hmac.new(
            _signing_key(SECRET_KEY, datestamp, REGION, SERVICE),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        query.append(("X-Amz-Signature", signature))

        request = _make_request(
            "GET",
            path,
            headers={
                "host": "localhost",
                "x-amz-content-sha256": UNSIGNED_PAYLOAD,
            },
            query=query,
        )
        auth = extract_sigv4_auth(request)
        payload_hash = await resolve_payload_hash(request)
        verify_sigv4(
            request,
            auth,
            SECRET_KEY,
            expected_region=REGION,
            expected_service=SERVICE,
            max_skew_seconds=900,
            payload_hash=payload_hash,
        )
        self.assertEqual(auth.source, "query")
        self.assertEqual(auth.expires, expires)
