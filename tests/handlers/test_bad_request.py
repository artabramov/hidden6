# tests/handlers/test_bad_request.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.errors import BadRequestError
from app.handlers import bad_request_handler


class TestBadRequestHandler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_400(self):
        request = MagicMock()
        exc = BadRequestError()

        response = await bad_request_handler(request, exc)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
