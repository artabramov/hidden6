# tests/routers/test_user_init.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.routers.user_init import user_init_router  # noqa: E402
from app.schemas.user_init import UserInitRequest  # noqa: E402


class TestUserInitRouter(unittest.IsolatedAsyncioTestCase):

    async def test_returns_201_with_credentials(self):
        data = UserInitRequest(master_password="Master-passphrase1")
        session = MagicMock()
        result = {
            "user_id": 1,
            "username": "root",
            "access_key_id": "access-key-id-value",
            "secret_access_key": "secret-access-key-value",
        }

        with patch(
            "app.routers.user_init.user_init",
            new_callable=AsyncMock,
            return_value=result,
        ) as mock_service:
            response = await user_init_router(data=data, session=session)

        mock_service.assert_awaited_once_with(
            master_password="Master-passphrase1",
            session=session,
        )
        self.assertEqual(response.user_id, 1)
        self.assertEqual(response.username, "root")
        self.assertEqual(response.access_key_id, "access-key-id-value")
        self.assertEqual(
            response.secret_access_key,
            "secret-access-key-value",
        )
