# tests/routers/test_gocryptfs_health.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.routers.gocryptfs_health import (  # noqa: E402
    gocryptfs_health_router,
)


class TestGocryptfsHealthRouter(unittest.IsolatedAsyncioTestCase):

    async def test_returns_snapshot_and_calls_service(self):
        payload = {
            "is_cipherdir_created": True,
            "is_cipherdir_mounted": False,
            "is_watchdog_alive": True,
            "unix_timestamp": 123,
            "timezone_name": "UTC",
        }

        with patch(
            "app.routers.gocryptfs_health.gocryptfs_health",
            new=AsyncMock(return_value=payload),
        ) as mock_service:
            response = await gocryptfs_health_router()

        mock_service.assert_awaited_once_with()
        self.assertTrue(response.is_cipherdir_created)
        self.assertFalse(response.is_cipherdir_mounted)
        self.assertTrue(response.is_watchdog_alive)
        self.assertEqual(response.unix_timestamp, 123)
        self.assertEqual(response.timezone_name, "UTC")
