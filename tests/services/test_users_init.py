# tests/services/test_users_init.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.constants import (  # noqa: E402
    USER_ACCESS_KEY_ID_LENGTH,
    USER_ROOT_USERNAME,
    USER_SECRET_ACCESS_KEY_LENGTH,
)
from app.errors import (  # noqa: E402
    ResourceConflictError,
    UnauthorizedError,
)
from app.hooks import Events  # noqa: E402
from app.locks import LockType  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.users_init import users_init  # noqa: E402

load_all_models()


class TestUsersInit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.users_init.log")
        self.log_patcher.start()

    def tearDown(self):
        self.log_patcher.stop()

    def _build_lock_context(self):
        ctx = AsyncMock()
        ctx.__aenter__.return_value = None
        ctx.__aexit__.return_value = None
        return ctx

    def _build_config(self):
        config = MagicMock()
        config.INSTALL_SECRETS = "/fake/secrets"
        config.GOCRYPTFS_PASSPHRASE_PATH = "/fake/secrets/passphrase.enc"
        return config

    async def test_raises_unauthorized_when_password_invalid(self):
        config = self._build_config()
        session = MagicMock()

        with (
            patch(
                "app.services.users_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.users_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.users_init.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.users_init.decrypt_passphrase",
                side_effect=ValueError("bad"),
            ),
            patch(
                "app.services.users_init.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(UnauthorizedError):
                await users_init("wrong-password", session)

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        emit_mock.assert_not_awaited()

    async def test_raises_conflict_when_root_exists(self):
        config = self._build_config()
        session = MagicMock()
        repo = MagicMock()
        repo.select = AsyncMock(
            return_value=User(username="root", is_root=True),
        )

        with (
            patch(
                "app.services.users_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.users_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.users_init.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.users_init.decrypt_passphrase",
                return_value=b"ok",
            ),
            patch(
                "app.services.users_init.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.users_init.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(ResourceConflictError):
                await users_init("master-password", session)

        repo.select.assert_awaited_once_with(User, is_root=True)
        emit_mock.assert_not_awaited()

    async def test_creates_root_user_and_key(self):
        config = self._build_config()
        session = MagicMock()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        async def insert_side_effect(obj, flush=True, commit=False):
            if isinstance(obj, User):
                obj.id = 1
            return obj

        repo.insert = AsyncMock(side_effect=insert_side_effect)

        with (
            patch(
                "app.services.users_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.users_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.users_init.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.users_init.decrypt_passphrase",
                return_value=b"ok",
            ),
            patch(
                "app.services.users_init.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.users_init.generate_random_string",
                side_effect=[
                    "access-key-id-20chars",
                    "secret-access-key-40-characters-xxxxxx",
                ],
            ) as random_mock,
            patch(
                "app.services.users_init.encrypt_string",
                return_value="enc-secret",
            ) as encrypt_mock,
            patch(
                "app.services.users_init.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            result = await users_init("master-password", session)

        self.assertEqual(
            result,
            {
                "user_id": 1,
                "username": USER_ROOT_USERNAME,
                "access_key_id": "access-key-id-20chars",
                "secret_access_key": (
                    "secret-access-key-40-characters-xxxxxx"
                ),
            },
        )
        random_mock.assert_any_call(USER_ACCESS_KEY_ID_LENGTH)
        random_mock.assert_any_call(USER_SECRET_ACCESS_KEY_LENGTH)
        encrypt_mock.assert_called_once_with(
            "secret-access-key-40-characters-xxxxxx",
        )
        self.assertEqual(repo.insert.await_count, 2)
        user_obj = repo.insert.await_args_list[0].args[0]
        key_obj = repo.insert.await_args_list[1].args[0]
        self.assertEqual(user_obj.username, USER_ROOT_USERNAME)
        self.assertTrue(user_obj.is_root)
        self.assertEqual(key_obj.user_id, 1)
        self.assertEqual(key_obj.access_key_id, "access-key-id-20chars")
        self.assertEqual(key_obj.secret_access_key_encrypted, "enc-secret")
        emit_mock.assert_awaited_once_with(Events.USERS_INITIALIZED, user_obj)
