# tests/routers/test_gocryptfs_passphrase.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.routers.gocryptfs_passphrase import (  # noqa: E402
    gocryptfs_passphrase_router,
)
from app.schemas.gocryptfs_passphrase import (  # noqa: E402
    GocryptfsPassphraseRequest,
)


class TestGocryptfsPassphraseRouter(unittest.IsolatedAsyncioTestCase):

    async def test_returns_passphrase_and_calls_service(self):
        data = GocryptfsPassphraseRequest(
            master_password="Master-passphrase1",
        )

        with patch(
            "app.routers.gocryptfs_passphrase.gocryptfs_passphrase",
            new_callable=AsyncMock,
            return_value="secret-gocryptfs-passphrase",
        ) as mock_service:
            response = await gocryptfs_passphrase_router(data=data)

        mock_service.assert_awaited_once_with(
            master_password="Master-passphrase1",
        )
        self.assertEqual(
            response.gocryptfs_passphrase,
            "secret-gocryptfs-passphrase",
        )
