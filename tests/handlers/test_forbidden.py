# tests/handlers/test_forbidden.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.errors import ForbiddenError
from app.handlers import forbidden_handler


class TestForbiddenHandler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_403(self):
        request = MagicMock()
        exc = ForbiddenError()

        response = await forbidden_handler(request, exc)

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )
