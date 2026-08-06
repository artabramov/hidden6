# tests/routers/test_gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.routers.gocryptfs_unmount import (  # noqa: E402
    gocryptfs_unmount_router,
)
from app.schemas.gocryptfs_unmount import (  # noqa: E402
    GocryptfsUnmountRequest,
)


class TestGocryptfsUnmountRouter(unittest.IsolatedAsyncioTestCase):

    async def test_returns_204_and_calls_service(self):
        data = GocryptfsUnmountRequest(
            master_password="Master-passphrase1",
        )

        with patch(
            "app.routers.gocryptfs_unmount.gocryptfs_unmount",
            new_callable=AsyncMock,
        ) as mock_service:
            response = await gocryptfs_unmount_router(data=data)

        mock_service.assert_awaited_once_with(
            master_password="Master-passphrase1",
        )
        self.assertEqual(response.status_code, 204)
