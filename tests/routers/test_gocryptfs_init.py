# tests/routers/test_gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.routers.gocryptfs_init import (  # noqa: E402
    gocryptfs_init_router,
)
from app.schemas.gocryptfs_init import (  # noqa: E402
    GocryptfsInitRequest,
)


class TestGocryptfsInitRouter(unittest.IsolatedAsyncioTestCase):

    async def test_returns_204_and_calls_service(self):
        data = GocryptfsInitRequest(
            master_password="Master-passphrase1",
        )

        with patch(
            "app.routers.gocryptfs_init.gocryptfs_init",
            new_callable=AsyncMock,
        ) as mock_service:
            response = await gocryptfs_init_router(data=data)

        mock_service.assert_awaited_once_with("Master-passphrase1")

        self.assertEqual(response.status_code, 204)
