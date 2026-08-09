# tests/handlers/test_bad_gateway.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.errors import BadGatewayError
from app.handlers import bad_gateway_handler


class TestBadGatewayHandler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_502(self):
        request = MagicMock()
        exc = BadGatewayError()

        response = await bad_gateway_handler(request, exc)

        self.assertEqual(
            response.status_code,
            status.HTTP_502_BAD_GATEWAY,
        )
