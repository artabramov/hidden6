# tests/routers/test_gocryptfs_rotate.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.routers.gocryptfs_rotate import (  # noqa: E402
    gocryptfs_rotate_router,
)
from app.schemas.gocryptfs_rotate import (  # noqa: E402
    GocryptfsRotateRequest,
)


class TestGocryptfsRotateRouter(unittest.IsolatedAsyncioTestCase):

    async def test_returns_204_and_calls_service(self):
        data = GocryptfsRotateRequest(
            current_master_password="Master-passphrase1",
            changed_master_password="Another-master-pass1",
        )

        with patch(
            "app.routers.gocryptfs_rotate.gocryptfs_rotate",
            new_callable=AsyncMock,
        ) as mock_service:
            response = await gocryptfs_rotate_router(data=data)

        mock_service.assert_awaited_once_with(
            current_master_password="Master-passphrase1",
            changed_master_password="Another-master-pass1",
        )
        self.assertEqual(response.status_code, 204)
