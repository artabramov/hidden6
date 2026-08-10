# tests/services/test_gocryptfs_rotate.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.errors import UnauthorizedError
from app.hooks import Events
from app.locks import LockType
from app.services.gocryptfs_rotate import gocryptfs_rotate


class TestGocryptfsRotate(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.gocryptfs_rotate.log")
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

    async def test_raises_unauthorized_when_current_password_wrong(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_rotate.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_rotate.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_rotate.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.gocryptfs_rotate.decrypt_passphrase",
                side_effect=ValueError,
            ) as decrypt_mock,
            patch(
                "app.services.gocryptfs_rotate.write",
                new=AsyncMock(),
            ) as write_mock,
            patch(
                "app.services.gocryptfs_rotate.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(UnauthorizedError):
                await gocryptfs_rotate("wrong", "NewMasterPass9")

        decrypt_mock.assert_called_once_with(b"encrypted", b"wrong")
        write_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()

    async def test_reencrypts_writes_and_emits_hook(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_rotate.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_rotate.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_rotate.read",
                new=AsyncMock(return_value=b"encrypted"),
            ),
            patch(
                "app.services.gocryptfs_rotate.decrypt_passphrase",
                return_value=b"plain",
            ) as decrypt_mock,
            patch(
                "app.services.gocryptfs_rotate.encrypt_passphrase",
                return_value=b"re-encrypted",
            ) as encrypt_mock,
            patch(
                "app.services.gocryptfs_rotate.write",
                new=AsyncMock(),
            ) as write_mock,
            patch(
                "app.services.gocryptfs_rotate.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            await gocryptfs_rotate("old", "NewMasterPass9")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        decrypt_mock.assert_called_once_with(b"encrypted", b"old")
        encrypt_mock.assert_called_once_with(b"plain", b"NewMasterPass9")
        write_mock.assert_awaited_once_with(
            config.GOCRYPTFS_PASSPHRASE_PATH,
            b"re-encrypted",
        )
        emit_mock.assert_awaited_once_with(Events.GOCRYPTFS_ROTATED)
