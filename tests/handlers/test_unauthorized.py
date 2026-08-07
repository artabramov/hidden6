# tests/handlers/test_unauthorized.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.errors import UnauthorizedError
from app.handlers import unauthorized_handler


class TestUnauthorizedHandler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_401(self):
        request = MagicMock()
        exc = UnauthorizedError()

        response = await unauthorized_handler(request, exc)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
