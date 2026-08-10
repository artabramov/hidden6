# app/security/sigv4.py
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Literal
from urllib.parse import parse_qsl

from fastapi import Request

from app.errors import ForbiddenError

# NOTE (ADR-20): S3 request authentication uses AWS Signature Version 4.
# Supports both Authorization-header and query-string (presigned URL)
# authentication. Signature validation failures raise ForbiddenError
# (403); HTTP 401 remains reserved for gocryptfs master-password
# failures.


ALGORITHM = "AWS4-HMAC-SHA256"
AWS4_REQUEST = "aws4_request"
UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"
EMPTY_PAYLOAD_HASH = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)

_STREAMING_PAYLOAD_PREFIX = "STREAMING-"

_AUTHORIZATION_RE = re.compile(
    r"^AWS4-HMAC-SHA256\s+"
    r"Credential=(?P<credential>[^ ,]+),\s*"
    r"SignedHeaders=(?P<signed_headers>[^ ,]+),\s*"
    r"Signature=(?P<signature>[0-9a-fA-F]{64})$",
)

_CREDENTIAL_RE = re.compile(
    r"^(?P<access_key_id>[^/]+)/"
    r"(?P<datestamp>\d{8})/"
    r"(?P<region>[^/]+)/"
    r"(?P<service>[^/]+)/"
    r"aws4_request$",
)

_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    "0123456789-._~",
)


@dataclass(frozen=True, slots=True)
class SigV4Auth:
    """Parsed SigV4 credential material from a request."""

    access_key_id: str
    datestamp: str
    region: str
    service: str
    signed_headers: tuple[str, ...]
    signature: str
    amz_date: str
    source: Literal["header", "query"]
    expires: int | None = None


def uri_encode(value: str, *, encode_slash: bool = True) -> str:
    """Percent-encode a value per the AWS SigV4 rules."""
    out: list[str] = []
    for char in value:
        if char in _UNRESERVED or (char == "/" and not encode_slash):
            out.append(char)
        else:
            out.append(f"%{ord(char):02X}")
    return "".join(out)


def extract_sigv4_auth(request: Request) -> SigV4Auth:
    """
    Extract SigV4 auth parameters from Authorization or query string.

    Raises:
        ForbiddenError: Auth material is missing or malformed.
    """
    authorization = request.headers.get("authorization")
    if authorization:
        return _parse_authorization_header(request, authorization)

    algorithm = request.query_params.get("X-Amz-Algorithm")
    if algorithm:
        return _parse_query_auth(request)

    raise ForbiddenError


def verify_sigv4(
    request: Request,
    auth: SigV4Auth,
    secret_access_key: str,
    *,
    expected_region: str,
    expected_service: str,
    max_skew_seconds: int,
    payload_hash: str,
) -> None:
    """
    Verify a SigV4 signature against the given request and secret.

    Raises:
        ForbiddenError: Scope, skew, expiry, or signature is invalid.
    """
    if auth.region != expected_region:
        raise ForbiddenError
    if auth.service != expected_service:
        raise ForbiddenError
    if auth.datestamp != auth.amz_date[:8]:
        raise ForbiddenError
    if "host" not in auth.signed_headers:
        raise ForbiddenError

    _assert_time_valid(auth, max_skew_seconds=max_skew_seconds)

    canonical_request = _canonical_request(
        request,
        auth,
        payload_hash=payload_hash,
    )
    credential_scope = "/".join((
        auth.datestamp,
        auth.region,
        auth.service,
        AWS4_REQUEST,
    ))
    string_to_sign = "\n".join((
        ALGORITHM,
        auth.amz_date,
        credential_scope,
        _sha256_hex(canonical_request.encode("utf-8")),
    ))
    signing_key = _derive_signing_key(
        secret_access_key,
        auth.datestamp,
        auth.region,
        auth.service,
    )
    expected = hmac.new(
        signing_key,
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, auth.signature.lower()):
        raise ForbiddenError


async def resolve_payload_hash(request: Request) -> str:
    """
    Resolve the payload hash used in the canonical request.

    Prefers x-amz-content-sha256 when present. Hex digests are checked
    against the request body; UNSIGNED-PAYLOAD and streaming markers are
    accepted as opaque signed values.
    """
    header_hash = request.headers.get("x-amz-content-sha256")
    if header_hash is None:
        body = await request.body()
        return _sha256_hex(body) if body else EMPTY_PAYLOAD_HASH

    if header_hash == UNSIGNED_PAYLOAD:
        return UNSIGNED_PAYLOAD

    if header_hash.startswith(_STREAMING_PAYLOAD_PREFIX):
        return header_hash

    if len(header_hash) == 64 and _is_hex(header_hash):
        body = await request.body()
        actual = _sha256_hex(body)
        if not hmac.compare_digest(actual, header_hash.lower()):
            raise ForbiddenError
        return header_hash.lower()

    raise ForbiddenError


def _parse_authorization_header(
    request: Request,
    authorization: str,
) -> SigV4Auth:
    match = _AUTHORIZATION_RE.match(authorization.strip())
    if match is None:
        raise ForbiddenError

    credential = _parse_credential(match.group("credential"))
    signed_headers = _parse_signed_headers(match.group("signed_headers"))
    amz_date = _amz_date_from_headers(request)

    return SigV4Auth(
        access_key_id=credential["access_key_id"],
        datestamp=credential["datestamp"],
        region=credential["region"],
        service=credential["service"],
        signed_headers=signed_headers,
        signature=match.group("signature").lower(),
        amz_date=amz_date,
        source="header",
    )


def _parse_query_auth(request: Request) -> SigV4Auth:
    params = request.query_params
    algorithm = params.get("X-Amz-Algorithm")
    credential_raw = params.get("X-Amz-Credential")
    amz_date = params.get("X-Amz-Date")
    signed_headers_raw = params.get("X-Amz-SignedHeaders")
    signature = params.get("X-Amz-Signature")
    expires_raw = params.get("X-Amz-Expires")

    if algorithm != ALGORITHM:
        raise ForbiddenError
    if not credential_raw or not amz_date or not signed_headers_raw:
        raise ForbiddenError
    if not signature or len(signature) != 64 or not _is_hex(signature):
        raise ForbiddenError
    if expires_raw is None:
        raise ForbiddenError

    try:
        expires = int(expires_raw)
    except ValueError as exc:
        raise ForbiddenError from exc
    if expires <= 0:
        raise ForbiddenError

    credential = _parse_credential(credential_raw)
    signed_headers = _parse_signed_headers(signed_headers_raw)

    return SigV4Auth(
        access_key_id=credential["access_key_id"],
        datestamp=credential["datestamp"],
        region=credential["region"],
        service=credential["service"],
        signed_headers=signed_headers,
        signature=signature.lower(),
        amz_date=amz_date,
        source="query",
        expires=expires,
    )


def _parse_credential(credential: str) -> dict[str, str]:
    match = _CREDENTIAL_RE.match(credential)
    if match is None:
        raise ForbiddenError
    return match.groupdict()


def _parse_signed_headers(raw: str) -> tuple[str, ...]:
    headers = tuple(part.strip().lower() for part in raw.split(";") if part)
    if not headers:
        raise ForbiddenError
    if headers != tuple(sorted(headers)):
        raise ForbiddenError
    return headers


def _amz_date_from_headers(request: Request) -> str:
    amz_date = request.headers.get("x-amz-date")
    if amz_date:
        if not _is_amz_date(amz_date):
            raise ForbiddenError
        return amz_date

    date_header = request.headers.get("date")
    if not date_header:
        raise ForbiddenError
    try:
        parsed = parsedate_to_datetime(date_header)
    except (TypeError, ValueError, IndexError) as exc:
        raise ForbiddenError from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _assert_time_valid(
    auth: SigV4Auth,
    *,
    max_skew_seconds: int,
) -> None:
    if not _is_amz_date(auth.amz_date):
        raise ForbiddenError

    try:
        signed_at = datetime.strptime(
            auth.amz_date,
            "%Y%m%dT%H%M%SZ",
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ForbiddenError from exc

    now = datetime.now(timezone.utc)
    delta = abs((now - signed_at).total_seconds())
    if delta > max_skew_seconds:
        raise ForbiddenError

    if auth.expires is not None:
        age = (now - signed_at).total_seconds()
        if age < 0 or age > auth.expires:
            raise ForbiddenError


def _canonical_request(
    request: Request,
    auth: SigV4Auth,
    *,
    payload_hash: str,
) -> str:
    return "\n".join((
        request.method.upper(),
        _canonical_uri(request.url.path),
        _canonical_query_string(request, auth),
        _canonical_headers(request, auth.signed_headers),
        ";".join(auth.signed_headers),
        payload_hash,
    ))


def _canonical_uri(path: str) -> str:
    if not path:
        return "/"
    return uri_encode(path, encode_slash=False)


def _canonical_query_string(request: Request, auth: SigV4Auth) -> str:
    raw_query = request.url.query
    pairs = parse_qsl(raw_query, keep_blank_values=True)

    encoded: list[tuple[str, str]] = []
    for key, value in pairs:
        if auth.source == "query" and key == "X-Amz-Signature":
            continue
        encoded.append((
            uri_encode(key, encode_slash=True),
            uri_encode(value, encode_slash=True),
        ))

    encoded.sort(key=lambda item: (item[0], item[1]))
    return "&".join(f"{key}={value}" for key, value in encoded)


def _canonical_headers(
    request: Request,
    signed_headers: tuple[str, ...],
) -> str:
    lines: list[str] = []
    for name in signed_headers:
        value = request.headers.get(name)
        if value is None:
            raise ForbiddenError
        lines.append(f"{name}:{_canonicalize_header_value(value)}")
    return "\n".join(lines) + "\n"


def _canonicalize_header_value(value: str) -> str:
    return " ".join(value.strip().split())


def _derive_signing_key(
    secret_access_key: str,
    datestamp: str,
    region: str,
    service: str,
) -> bytes:
    key = ("AWS4" + secret_access_key).encode("utf-8")
    key = _hmac_sha256(key, datestamp)
    key = _hmac_sha256(key, region)
    key = _hmac_sha256(key, service)
    return _hmac_sha256(key, AWS4_REQUEST)


def _hmac_sha256(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_hex(value: str) -> bool:
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _is_amz_date(value: str) -> bool:
    if len(value) != 16 or value[8] != "T" or not value.endswith("Z"):
        return False
    try:
        datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return False
    return True
