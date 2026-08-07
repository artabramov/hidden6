# tests/services/test_gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.errors import (
    UnauthorizedError,
    ResourceConflictError,
    ServiceUnavailableError,
)
from app.hooks import Events
from app.locks import LockType
from app.services.gocryptfs_unmount import gocryptfs_unmount


class TestGocryptfsUnmount(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # app.db.engine calls get_config() at module level, so we cannot
        # patch it via unittest.mock.patch (the import itself would fail).
        # Instead, inject a fake module into sys.modules before the lazy
        # import inside gocryptfs_unmount runs, then restore afterwards.
        self.engine_mock = MagicMock()
        self._original_engine_module = sys.modules.get("app.db.engine")
        fake_engine_module = types.ModuleType("app.db.engine")
        fake_engine_module.engine = self.engine_mock
        sys.modules["app.db.engine"] = fake_engine_module
        self.addCleanup(self._restore_engine_module)

    def _restore_engine_module(self):
        if self._original_engine_module is not None:
            sys.modules["app.db.engine"] = self._original_engine_module
        else:
            sys.modules.pop("app.db.engine", None)

    def _build_lock_context(self):
        lock_context = AsyncMock()
        lock_context.__aenter__.return_value = None
        lock_context.__aexit__.return_value = None
        return lock_context

    def _build_config(self):
        config = MagicMock()
        config.INSTALL_SECRETS = "/fake/secrets"
        config.INSTALL_CIPHERDIR = "/fake/cipherdir"
        config.INSTALL_MOUNTPOINT = "/fake/mountpoint"
        config.GOCRYPTFS_PASSPHRASE_PATH = "/fake/secrets/passphrase.enc"
        return config

    async def test_raises_service_unavailable_when_cipherdir_uninitialized(
        self,
    ):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_unmount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_unmount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_unmount.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ) as created_mock,
            patch(
                "app.services.gocryptfs_unmount.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_unmount.cipherdir_unmount",
                new=AsyncMock(),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_unmount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(ServiceUnavailableError):
                await gocryptfs_unmount("master-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        created_mock.assert_awaited_once_with(config.INSTALL_CIPHERDIR)
        isfile_mock.assert_not_awaited()
        unmount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()
        self.engine_mock.sync_engine.dispose.assert_not_called()

    async def test_raises_service_unavailable_when_passphrase_missing(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_unmount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_unmount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_unmount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.isfile",
                new=AsyncMock(return_value=False),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_unmount.ismount",
                new=AsyncMock(),
            ) as ismount_mock,
            patch(
                "app.services.gocryptfs_unmount.cipherdir_unmount",
                new=AsyncMock(),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_unmount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(ServiceUnavailableError):
                await gocryptfs_unmount("master-password")

        isfile_mock.assert_awaited_once_with(
            config.GOCRYPTFS_PASSPHRASE_PATH,
        )
        ismount_mock.assert_not_awaited()
        unmount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()

    async def test_raises_conflict_when_mountpoint_not_mounted(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_unmount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_unmount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_unmount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.ismount",
                new=AsyncMock(return_value=False),
            ) as ismount_mock,
            patch(
                "app.services.gocryptfs_unmount.read",
                new=AsyncMock(),
            ) as read_mock,
            patch(
                "app.services.gocryptfs_unmount.cipherdir_unmount",
                new=AsyncMock(),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_unmount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(ResourceConflictError):
                await gocryptfs_unmount("master-password")

        ismount_mock.assert_awaited_once_with(config.INSTALL_MOUNTPOINT)
        read_mock.assert_not_awaited()
        unmount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()

    async def test_raises_unauthorized_when_master_password_incorrect(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_unmount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_unmount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_unmount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.ismount",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.read",
                new=AsyncMock(return_value=b"encrypted-passphrase"),
            ) as read_mock,
            patch(
                "app.services.gocryptfs_unmount.decrypt_passphrase",
                side_effect=ValueError,
            ) as decrypt_mock,
            patch(
                "app.services.gocryptfs_unmount.cipherdir_unmount",
                new=AsyncMock(),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_unmount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(UnauthorizedError):
                await gocryptfs_unmount("wrong-password")

        read_mock.assert_awaited_once_with(
            config.GOCRYPTFS_PASSPHRASE_PATH,
        )
        decrypt_mock.assert_called_once_with(
            b"encrypted-passphrase",
            b"wrong-password",
        )
        unmount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()
        self.engine_mock.sync_engine.dispose.assert_not_called()

    async def test_unmounts_disposes_engine_and_emits_hook(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_unmount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_unmount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_unmount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.ismount",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.read",
                new=AsyncMock(return_value=b"encrypted-passphrase"),
            ),
            patch(
                "app.services.gocryptfs_unmount.decrypt_passphrase",
                return_value=b"decrypted-passphrase",
            ) as decrypt_mock,
            patch(
                "app.services.gocryptfs_unmount.cipherdir_unmount",
                new=AsyncMock(),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_unmount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            await gocryptfs_unmount("master-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        decrypt_mock.assert_called_once_with(
            b"encrypted-passphrase",
            b"master-password",
        )
        self.engine_mock.sync_engine.dispose.assert_called_once_with()
        unmount_mock.assert_awaited_once_with(
            mountpoint=config.INSTALL_MOUNTPOINT,
        )
        emit_mock.assert_awaited_once_with(
            Events.GOCRYPTFS_UNMOUNT_COMPLETED,
        )

    async def test_engine_dispose_called_before_cipherdir_unmount(self):
        config = self._build_config()
        call_order = []

        def record_dispose():
            call_order.append("dispose")

        async def record_unmount(**_kwargs):
            call_order.append("unmount")

        self.engine_mock.sync_engine.dispose.side_effect = record_dispose

        with (
            patch(
                "app.services.gocryptfs_unmount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_unmount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_unmount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.ismount",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_unmount.read",
                new=AsyncMock(return_value=b"encrypted-passphrase"),
            ),
            patch(
                "app.services.gocryptfs_unmount.decrypt_passphrase",
                return_value=b"decrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_unmount.cipherdir_unmount",
                new=record_unmount,
            ),
            patch(
                "app.services.gocryptfs_unmount.hooks.emit",
                new=AsyncMock(),
            ),
        ):
            await gocryptfs_unmount("master-password")

        self.assertEqual(call_order, ["dispose", "unmount"])
