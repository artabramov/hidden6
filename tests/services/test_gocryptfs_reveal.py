# tests/services/test_gocryptfs_reveal.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.errors import UnauthorizedError
from app.hooks import Events
from app.locks import LockType
from app.services.gocryptfs_reveal import gocryptfs_reveal


class TestGocryptfsReveal(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.gocryptfs_reveal.log")
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

    async def test_raises_unauthorized_when_master_password_incorrect(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_reveal.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_reveal.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_reveal.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.gocryptfs_reveal.decrypt_passphrase",
                side_effect=ValueError,
            ) as decrypt_mock,
            patch(
                "app.services.gocryptfs_reveal.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(UnauthorizedError):
                await gocryptfs_reveal("wrong-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.READ,
        )
        decrypt_mock.assert_called_once_with(
            b"encrypted",
            b"wrong-password",
        )
        emit_mock.assert_not_awaited()

    async def test_returns_decrypted_passphrase_and_emits_hook(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_reveal.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_reveal.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_reveal.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.gocryptfs_reveal.decrypt_passphrase",
                return_value=b"plain-passphrase",
            ) as decrypt_mock,
            patch(
                "app.services.gocryptfs_reveal.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            result = await gocryptfs_reveal("master-password")

        decrypt_mock.assert_called_once_with(
            b"encrypted",
            b"master-password",
        )
        self.assertEqual(result, "plain-passphrase")
        emit_mock.assert_awaited_once_with(Events.GOCRYPTFS_REVEALED)
