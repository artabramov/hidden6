# tests/services/test_gocryptfs_mount.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.errors import (
    BadRequestError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.hooks import Events
from app.locks import LockType
from app.services.gocryptfs_mount import gocryptfs_mount


class TestGocryptfsMount(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.gocryptfs_mount.log")
        self.log_mock = self.log_patcher.start()

    def tearDown(self):
        self.log_patcher.stop()

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
        config.MOUNTPOINT_DB_DIR = "/fake/mountpoint/db"
        config.MOUNTPOINT_BUCKETS_DIR = "/fake/mountpoint/buckets"
        config.MOUNTPOINT_VERSIONS_DIR = "/fake/mountpoint/versions"
        config.MOUNTPOINT_TMP_DIR = "/fake/mountpoint/tmp"
        config.SQLITE_PATH = "/fake/mountpoint/db/hidden.db"
        return config

    async def test_raises_not_found_when_cipherdir_uninitialized(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_mount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_mount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_mount.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ) as created_mock,
            patch(
                "app.services.gocryptfs_mount.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_mount.cipherdir_mount",
                new=AsyncMock(),
            ) as mount_mock,
            patch(
                "app.services.gocryptfs_mount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(ResourceNotFoundError):
                await gocryptfs_mount("master-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        created_mock.assert_awaited_once_with(config.INSTALL_CIPHERDIR)
        isfile_mock.assert_not_awaited()
        mount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()

    async def test_raises_not_found_when_passphrase_missing(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_mount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_mount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_mount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.isfile",
                new=AsyncMock(return_value=False),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_mount.ismount",
                new=AsyncMock(),
            ) as ismount_mock,
            patch(
                "app.services.gocryptfs_mount.cipherdir_mount",
                new=AsyncMock(),
            ) as mount_mock,
            patch(
                "app.services.gocryptfs_mount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(ResourceNotFoundError):
                await gocryptfs_mount("master-password")

        isfile_mock.assert_awaited_once_with(
            config.GOCRYPTFS_PASSPHRASE_PATH,
        )
        ismount_mock.assert_not_awaited()
        mount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()

    async def test_raises_conflict_when_already_mounted(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_mount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_mount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_mount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.ismount",
                new=AsyncMock(return_value=True),
            ) as ismount_mock,
            patch(
                "app.services.gocryptfs_mount.read",
                new=AsyncMock(),
            ) as read_mock,
            patch(
                "app.services.gocryptfs_mount.cipherdir_mount",
                new=AsyncMock(),
            ) as mount_mock,
            patch(
                "app.services.gocryptfs_mount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(ResourceConflictError):
                await gocryptfs_mount("master-password")

        ismount_mock.assert_awaited_once_with(config.INSTALL_MOUNTPOINT)
        read_mock.assert_not_awaited()
        mount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()

    async def test_raises_bad_request_when_master_password_incorrect(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_mount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_mount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_mount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.ismount",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_mount.read",
                new=AsyncMock(return_value=b"encrypted-passphrase"),
            ) as read_mock,
            patch(
                "app.services.gocryptfs_mount.decrypt_passphrase",
                side_effect=ValueError,
            ) as decrypt_mock,
            patch(
                "app.services.gocryptfs_mount.cipherdir_mount",
                new=AsyncMock(),
            ) as mount_mock,
            patch(
                "app.services.gocryptfs_mount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(BadRequestError):
                await gocryptfs_mount("wrong-password")

        read_mock.assert_awaited_once_with(
            config.GOCRYPTFS_PASSPHRASE_PATH,
        )
        decrypt_mock.assert_called_once_with(
            b"encrypted-passphrase",
            b"wrong-password",
        )
        mount_mock.assert_not_awaited()
        emit_mock.assert_not_awaited()

    async def test_mounts_creates_directories_checks_integrity_and_emits(
        self,
    ):
        config = self._build_config()
        isdir_mock = AsyncMock(
            side_effect=[False, False, False, False, False],
        )
        mkdir_mock = AsyncMock()

        with (
            patch(
                "app.services.gocryptfs_mount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_mount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_mount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.ismount",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_mount.read",
                new=AsyncMock(return_value=b"encrypted-passphrase"),
            ),
            patch(
                "app.services.gocryptfs_mount.isdir",
                new=isdir_mock,
            ),
            patch(
                "app.services.gocryptfs_mount.mkdir",
                new=mkdir_mock,
            ),
            patch(
                "app.services.gocryptfs_mount.decrypt_passphrase",
                return_value=b"decrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_mount.cipherdir_mount",
                new=AsyncMock(),
            ) as mount_mock,
            patch(
                "app.services.gocryptfs_mount.cipherdir_unmount",
                new=AsyncMock(),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_mount.check_db_integrity",
                new=AsyncMock(),
            ) as integrity_mock,
            patch(
                "app.services.gocryptfs_mount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            await gocryptfs_mount("master-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        mount_mock.assert_awaited_once_with(
            passphrase="decrypted-passphrase",
            cipherdir=config.INSTALL_CIPHERDIR,
            mountpoint=config.INSTALL_MOUNTPOINT,
        )
        mkdir_mock.assert_any_await(config.INSTALL_MOUNTPOINT)
        mkdir_mock.assert_any_await(config.MOUNTPOINT_DB_DIR)
        mkdir_mock.assert_any_await(config.MOUNTPOINT_BUCKETS_DIR)
        mkdir_mock.assert_any_await(config.MOUNTPOINT_VERSIONS_DIR)
        mkdir_mock.assert_any_await(config.MOUNTPOINT_TMP_DIR)
        self.assertEqual(mkdir_mock.await_count, 5)
        integrity_mock.assert_awaited_once_with(config.SQLITE_PATH)
        unmount_mock.assert_not_awaited()
        emit_mock.assert_awaited_once_with(
            Events.GOCRYPTFS_MOUNT_COMPLETED,
        )

    async def test_rolls_back_mount_when_integrity_check_fails(self):
        config = self._build_config()
        isdir_mock = AsyncMock(return_value=True)

        with (
            patch(
                "app.services.gocryptfs_mount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_mount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_mount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.ismount",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_mount.read",
                new=AsyncMock(return_value=b"encrypted-passphrase"),
            ),
            patch(
                "app.services.gocryptfs_mount.isdir",
                new=isdir_mock,
            ),
            patch(
                "app.services.gocryptfs_mount.mkdir",
                new=AsyncMock(),
            ),
            patch(
                "app.services.gocryptfs_mount.decrypt_passphrase",
                return_value=b"decrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_mount.cipherdir_mount",
                new=AsyncMock(),
            ) as mount_mock,
            patch(
                "app.services.gocryptfs_mount.cipherdir_unmount",
                new=AsyncMock(),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_mount.check_db_integrity",
                new=AsyncMock(
                    side_effect=RuntimeError(
                        "SQLite integrity check failed: Page 3 is never used"
                    ),
                ),
            ),
            patch(
                "app.services.gocryptfs_mount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(RuntimeError) as cm:
                await gocryptfs_mount("master-password")

        self.assertIn("integrity check failed", str(cm.exception))
        mount_mock.assert_awaited_once()
        unmount_mock.assert_awaited_once_with(config.INSTALL_MOUNTPOINT)
        emit_mock.assert_not_awaited()

    async def test_logs_rollback_failure_when_unmount_fails(self):
        config = self._build_config()
        isdir_mock = AsyncMock(return_value=True)

        with (
            patch(
                "app.services.gocryptfs_mount.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_mount.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_mount.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.isfile",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.services.gocryptfs_mount.ismount",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_mount.read",
                new=AsyncMock(return_value=b"encrypted-passphrase"),
            ),
            patch(
                "app.services.gocryptfs_mount.isdir",
                new=isdir_mock,
            ),
            patch(
                "app.services.gocryptfs_mount.mkdir",
                new=AsyncMock(),
            ),
            patch(
                "app.services.gocryptfs_mount.decrypt_passphrase",
                return_value=b"decrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_mount.cipherdir_mount",
                new=AsyncMock(),
            ),
            patch(
                "app.services.gocryptfs_mount.cipherdir_unmount",
                new=AsyncMock(side_effect=OSError("unmount failed")),
            ) as unmount_mock,
            patch(
                "app.services.gocryptfs_mount.check_db_integrity",
                new=AsyncMock(
                    side_effect=RuntimeError("db integrity failed"),
                ),
            ),
            patch(
                "app.services.gocryptfs_mount.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(RuntimeError) as cm:
                await gocryptfs_mount("master-password")

        self.assertEqual(cm.exception.args[0], "db integrity failed")
        unmount_mock.assert_awaited_once_with(config.INSTALL_MOUNTPOINT)
        emit_mock.assert_not_awaited()
        self.log_mock.exception.assert_any_call(
            "msg=%s",
            "gocryptfs_mount:failed",
        )
        self.log_mock.exception.assert_any_call(
            "msg=%s",
            "gocryptfs_mount:rollback_failed",
        )
