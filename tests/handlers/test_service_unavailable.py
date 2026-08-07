# tests/handlers/test_service_unavailable.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.errors import ServiceUnavailableError
from app.handlers import service_unavailable_handler


class TestServiceUnavailableHandler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_503(self):
        request = MagicMock()
        exc = ServiceUnavailableError()

        response = await service_unavailable_handler(request, exc)

        self.assertEqual(
            response.status_code,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
