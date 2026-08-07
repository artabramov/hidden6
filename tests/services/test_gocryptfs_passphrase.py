# tests/services/test_gocryptfs_passphrase.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.errors import ServiceUnavailableError, UnauthorizedError
from app.locks import LockType
from app.services.gocryptfs_passphrase import gocryptfs_passphrase


class TestGocryptfsPassphrase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.gocryptfs_passphrase.log")
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
        config.INSTALL_CIPHERDIR = "/fake/cipherdir"
        config.GOCRYPTFS_PASSPHRASE_PATH = "/fake/secrets/passphrase.enc"
        return config

    async def test_raises_service_unavailable_when_cipherdir_uninitialized(
        self,
    ):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_passphrase.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_passphrase.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_passphrase.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ) as created_mock,
            patch(
                "app.services.gocryptfs_passphrase.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
        ):
            with self.assertRaises(ServiceUnavailableError):
                await gocryptfs_passphrase("master-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        created_mock.assert_awaited_once_with(config.INSTALL_CIPHERDIR)
        isfile_mock.assert_not_awaited()

    async def test_raises_service_unavailable_when_passphrase_missing(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_passphrase.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_passphrase.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_passphrase.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_passphrase.isfile",
                new=AsyncMock(return_value=False),
            ) as isfile_mock,
        ):
            with self.assertRaises(ServiceUnavailableError):
                await gocryptfs_passphrase("master-password")

        isfile_mock.assert_awaited_once_with(
            config.GOCRYPTFS_PASSPHRASE_PATH,
        )

    async def test_raises_unauthorized_when_master_password_incorrect(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_passphrase.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_passphrase.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_passphrase.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_passphrase.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_passphrase.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.gocryptfs_passphrase.decrypt_passphrase",
                side_effect=ValueError,
            ) as decrypt_mock,
        ):
            with self.assertRaises(UnauthorizedError):
                await gocryptfs_passphrase("wrong-password")

        decrypt_mock.assert_called_once_with(
            b"encrypted",
            b"wrong-password",
        )

    async def test_returns_decrypted_passphrase(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_passphrase.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_passphrase.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_passphrase.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_passphrase.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_passphrase.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.gocryptfs_passphrase.decrypt_passphrase",
                return_value=b"plain-passphrase",
            ) as decrypt_mock,
        ):
            result = await gocryptfs_passphrase("master-password")

        decrypt_mock.assert_called_once_with(
            b"encrypted",
            b"master-password",
        )
        self.assertEqual(result, "plain-passphrase")
