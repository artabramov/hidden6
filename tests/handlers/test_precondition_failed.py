# tests/handlers/test_precondition_failed.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from fastapi import status

from app.errors import PreconditionFailedError
from app.handlers import precondition_failed_handler


class TestPreconditionFailedHandler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_412(self):
        request = MagicMock()
        exc = PreconditionFailedError()

        response = await precondition_failed_handler(request, exc)

        self.assertEqual(
            response.status_code,
            status.HTTP_412_PRECONDITION_FAILED,
        )
