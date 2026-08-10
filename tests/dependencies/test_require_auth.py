# tests/dependencies/test_require_auth.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import hmac
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from starlette.requests import Request

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.errors import ForbiddenError  # noqa: E402
from app.security.sigv4 import ALGORITHM, UNSIGNED_PAYLOAD  # noqa: E402
import app.dependencies.require_auth as require_auth_mod  # noqa: E402


ACCESS_KEY = "M2im2i3IdV1IJkYPpfRK"
SECRET_KEY = "VnFoYMQzvX0p8uDY5laIxEOw6XMHW7VpdFL2Vllg"
REGION = "us-east-1"
SERVICE = "s3"


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret: str, datestamp: str) -> bytes:
    key = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    key = _hmac(key, REGION)
    key = _hmac(key, SERVICE)
    return _hmac(key, "aws4_request")


def _signed_get_request() -> Request:
    amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    datestamp = amz_date[:8]
    payload_hash = UNSIGNED_PAYLOAD
    headers = {
        "host": "localhost",
        "x-amz-date": amz_date,
        "x-amz-content-sha256": payload_hash,
    }
    signed = "host;x-amz-content-sha256;x-amz-date"
    canonical_headers = (
        "host:localhost\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{amz_date}\n"
    )
    canonical_request = "\n".join((
        "GET",
        "/bucket",
        "",
        canonical_headers,
        signed,
        payload_hash,
    ))
    scope = f"{datestamp}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = "\n".join((
        ALGORITHM,
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ))
    signature = hmac.new(
        _signing_key(SECRET_KEY, datestamp),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers["authorization"] = (
        f"{ALGORITHM} Credential={ACCESS_KEY}/{scope}, "
        f"SignedHeaders={signed}, Signature={signature}"
    )

    header_list = [
        (k.lower().encode("latin-1"), v.encode("latin-1"))
        for k, v in headers.items()
    ]
    scope_asgi = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/bucket",
        "raw_path": b"/bucket",
        "query_string": b"",
        "headers": header_list,
        "client": ("127.0.0.1", 123),
        "server": ("testserver", 80),
    }

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope_asgi, receive)


class TestRequireAuth(unittest.IsolatedAsyncioTestCase):
    async def test_returns_user_when_signature_valid(self):
        request = _signed_get_request()
        session = MagicMock()
        user = MagicMock()
        user.is_enabled = True
        key = MagicMock()
        key.is_enabled = True
        key.user_id = 1
        key.secret_access_key_encrypted = "encrypted"

        repo = MagicMock()
        repo.select = AsyncMock(side_effect=[key, user])

        with (
            patch(
                "app.dependencies.require_auth.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.dependencies.require_auth.decrypt_string",
                return_value=SECRET_KEY,
            ),
            patch(
                "app.dependencies.require_auth.get_config",
            ) as get_config,
        ):
            get_config.return_value.S3_REGION = REGION
            get_config.return_value.S3_SERVICE = SERVICE
            get_config.return_value.S3_SIGV4_MAX_SKEW_SECONDS = 900

            result = await require_auth_mod.require_auth(request, session)

        self.assertIs(result, user)
        self.assertEqual(repo.select.await_count, 2)

    async def test_raises_when_key_missing(self):
        request = _signed_get_request()
        session = MagicMock()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        with (
            patch(
                "app.dependencies.require_auth.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.dependencies.require_auth.get_config",
            ) as get_config,
        ):
            get_config.return_value.S3_REGION = REGION
            get_config.return_value.S3_SERVICE = SERVICE
            get_config.return_value.S3_SIGV4_MAX_SKEW_SECONDS = 900

            with self.assertRaises(ForbiddenError):
                await require_auth_mod.require_auth(request, session)
