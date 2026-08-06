# tests/services/test_gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.constants import GOCRYPTFS_PASSPHRASE_LENGTH
from app.errors import ResourceConflictError
from app.hooks import Events
from app.locks import LockType
from app.services.gocryptfs_init import gocryptfs_init


class TestGocryptfsInit(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.gocryptfs_init.log")
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
        config.FERNET_ENCRYPTION_KEY_PATH = "/fake/secrets/fernet.key"
        return config

    def _expected_cleanup_paths(self, config):
        return [
            config.GOCRYPTFS_PASSPHRASE_PATH,
            os.path.join(config.INSTALL_CIPHERDIR, "gocryptfs.conf"),
            os.path.join(config.INSTALL_CIPHERDIR, "gocryptfs.diriv"),
            config.FERNET_ENCRYPTION_KEY_PATH,
        ]

    async def test_raises_conflict_when_cipherdir_already_initialized(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ) as created_mock,
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_init.write",
                new=AsyncMock(),
            ) as write_mock,
            patch(
                "app.services.gocryptfs_init.delete",
                new=AsyncMock(),
            ) as delete_mock,
            patch(
                "app.services.gocryptfs_init.cipherdir_create",
                new=AsyncMock(),
            ) as create_mock,
            patch(
                "app.services.gocryptfs_init.generate_random_string",
            ) as random_mock,
            patch(
                "app.services.gocryptfs_init.encrypt_passphrase",
            ) as encrypt_mock,
            patch(
                "app.services.gocryptfs_init.generate_fernet_key",
            ) as fernet_mock,
        ):
            with self.assertRaises(ResourceConflictError):
                await gocryptfs_init("master-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        created_mock.assert_awaited_once_with(config.INSTALL_CIPHERDIR)
        isfile_mock.assert_not_awaited()
        write_mock.assert_not_awaited()
        delete_mock.assert_not_awaited()
        create_mock.assert_not_awaited()
        random_mock.assert_not_called()
        encrypt_mock.assert_not_called()
        fernet_mock.assert_not_called()

    async def test_raises_conflict_when_passphrase_already_exists(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(side_effect=[True]),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_init.write",
                new=AsyncMock(),
            ) as write_mock,
            patch(
                "app.services.gocryptfs_init.delete",
                new=AsyncMock(),
            ) as delete_mock,
            patch(
                "app.services.gocryptfs_init.cipherdir_create",
                new=AsyncMock(),
            ) as create_mock,
        ):
            with self.assertRaises(ResourceConflictError):
                await gocryptfs_init("master-password")

        isfile_mock.assert_awaited_once_with(config.GOCRYPTFS_PASSPHRASE_PATH)
        write_mock.assert_not_awaited()
        delete_mock.assert_not_awaited()
        create_mock.assert_not_awaited()

    async def test_raises_conflict_when_fernet_key_already_exists(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(side_effect=[False, True]),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_init.write",
                new=AsyncMock(),
            ) as write_mock,
            patch(
                "app.services.gocryptfs_init.delete",
                new=AsyncMock(),
            ) as delete_mock,
            patch(
                "app.services.gocryptfs_init.cipherdir_create",
                new=AsyncMock(),
            ) as create_mock,
        ):
            with self.assertRaises(ResourceConflictError):
                await gocryptfs_init("master-password")

        self.assertEqual(isfile_mock.await_count, 2)
        isfile_mock.assert_any_await(config.GOCRYPTFS_PASSPHRASE_PATH)
        isfile_mock.assert_any_await(config.FERNET_ENCRYPTION_KEY_PATH)
        write_mock.assert_not_awaited()
        delete_mock.assert_not_awaited()
        create_mock.assert_not_awaited()

    async def test_creates_cipherdir_and_writes_all_secrets(self):
        config = self._build_config()
        write_mock = AsyncMock()

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ) as lock_mock,
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ) as created_mock,
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(side_effect=[False, False]),
            ) as isfile_mock,
            patch(
                "app.services.gocryptfs_init.generate_random_string",
                return_value="generated-passphrase",
            ) as random_mock,
            patch(
                "app.services.gocryptfs_init.encrypt_passphrase",
                return_value=b"encrypted-passphrase",
            ) as encrypt_mock,
            patch(
                "app.services.gocryptfs_init.generate_fernet_key",
                return_value="generated-fernet-key",
            ) as fernet_mock,
            patch(
                "app.services.gocryptfs_init.write",
                new=write_mock,
            ),
            patch(
                "app.services.gocryptfs_init.cipherdir_create",
                new=AsyncMock(),
            ) as create_mock,
            patch(
                "app.services.gocryptfs_init.delete",
                new=AsyncMock(),
            ) as delete_mock,
            patch(
                "app.services.gocryptfs_init.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            await gocryptfs_init("master-password")

        lock_mock.assert_called_once_with(
            config.INSTALL_SECRETS,
            LockType.WRITE,
        )
        created_mock.assert_awaited_once_with(config.INSTALL_CIPHERDIR)
        self.assertEqual(isfile_mock.await_count, 2)
        random_mock.assert_called_once_with(GOCRYPTFS_PASSPHRASE_LENGTH)
        encrypt_mock.assert_called_once_with(
            b"generated-passphrase",
            b"master-password",
        )
        fernet_mock.assert_called_once_with()

        self.assertEqual(write_mock.await_count, 2)
        write_mock.assert_any_await(
            config.GOCRYPTFS_PASSPHRASE_PATH,
            b"encrypted-passphrase",
        )
        write_mock.assert_any_await(
            config.FERNET_ENCRYPTION_KEY_PATH,
            b"generated-fernet-key",
        )

        create_mock.assert_awaited_once_with(
            "generated-passphrase",
            config.INSTALL_CIPHERDIR,
        )
        delete_mock.assert_not_awaited()
        emit_mock.assert_awaited_once_with(
            Events.GOCRYPTFS_INIT_COMPLETED,
        )

    async def test_cleans_up_when_first_write_fails(self):
        config = self._build_config()
        delete_mock = AsyncMock()
        write_mock = AsyncMock(
            side_effect=[RuntimeError("write passphrase failed")],
        )

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(side_effect=[False, False]),
            ),
            patch(
                "app.services.gocryptfs_init.generate_random_string",
                return_value="generated-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.encrypt_passphrase",
                return_value=b"encrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.generate_fernet_key",
                return_value="generated-fernet-key",
            ),
            patch(
                "app.services.gocryptfs_init.write",
                new=write_mock,
            ),
            patch(
                "app.services.gocryptfs_init.cipherdir_create",
                new=AsyncMock(),
            ) as create_mock,
            patch(
                "app.services.gocryptfs_init.delete",
                new=delete_mock,
            ),
        ):
            with self.assertRaises(RuntimeError):
                await gocryptfs_init("master-password")

        create_mock.assert_not_awaited()
        self.assertEqual(delete_mock.await_count, 4)
        for path in self._expected_cleanup_paths(config):
            delete_mock.assert_any_await(path)

    async def test_cleans_up_when_cipherdir_create_fails(self):
        config = self._build_config()
        delete_mock = AsyncMock()

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(side_effect=[False, False]),
            ),
            patch(
                "app.services.gocryptfs_init.generate_random_string",
                return_value="generated-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.encrypt_passphrase",
                return_value=b"encrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.generate_fernet_key",
                return_value="generated-fernet-key",
            ),
            patch(
                "app.services.gocryptfs_init.write",
                new=AsyncMock(),
            ) as write_mock,
            patch(
                "app.services.gocryptfs_init.cipherdir_create",
                new=AsyncMock(side_effect=RuntimeError("init failed")),
            ) as create_mock,
            patch(
                "app.services.gocryptfs_init.delete",
                new=delete_mock,
            ),
        ):
            with self.assertRaises(RuntimeError):
                await gocryptfs_init("master-password")

        self.assertEqual(write_mock.await_count, 1)
        create_mock.assert_awaited_once_with(
            "generated-passphrase",
            config.INSTALL_CIPHERDIR,
        )
        self.assertEqual(delete_mock.await_count, 4)
        for path in self._expected_cleanup_paths(config):
            delete_mock.assert_any_await(path)

    async def test_cleans_up_when_fernet_key_write_fails(self):
        config = self._build_config()
        delete_mock = AsyncMock()
        write_mock = AsyncMock(
            side_effect=[None, RuntimeError("fernet write failed")],
        )

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(side_effect=[False, False]),
            ),
            patch(
                "app.services.gocryptfs_init.generate_random_string",
                return_value="generated-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.encrypt_passphrase",
                return_value=b"encrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.generate_fernet_key",
                return_value="generated-fernet-key",
            ),
            patch(
                "app.services.gocryptfs_init.write",
                new=write_mock,
            ),
            patch(
                "app.services.gocryptfs_init.cipherdir_create",
                new=AsyncMock(),
            ),
            patch(
                "app.services.gocryptfs_init.delete",
                new=delete_mock,
            ),
        ):
            with self.assertRaises(RuntimeError):
                await gocryptfs_init("master-password")

        self.assertEqual(write_mock.await_count, 2)
        self.assertEqual(delete_mock.await_count, 4)
        for path in self._expected_cleanup_paths(config):
            delete_mock.assert_any_await(path)

    async def test_does_not_emit_hook_on_failure(self):
        config = self._build_config()

        with (
            patch(
                "app.services.gocryptfs_init.get_config",
                return_value=config,
            ),
            patch(
                "app.services.gocryptfs_init.locks.lock_directory",
                return_value=self._build_lock_context(),
            ),
            patch(
                "app.services.gocryptfs_init.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.services.gocryptfs_init.isfile",
                new=AsyncMock(side_effect=[False, False]),
            ),
            patch(
                "app.services.gocryptfs_init.generate_random_string",
                return_value="generated-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.encrypt_passphrase",
                return_value=b"encrypted-passphrase",
            ),
            patch(
                "app.services.gocryptfs_init.generate_fernet_key",
                return_value="generated-fernet-key",
            ),
            patch(
                "app.services.gocryptfs_init.write",
                new=AsyncMock(
                    side_effect=[RuntimeError("write failed")],
                ),
            ),
            patch(
                "app.services.gocryptfs_init.delete",
                new=AsyncMock(),
            ),
            patch(
                "app.services.gocryptfs_init.hooks.emit",
                new=AsyncMock(),
            ) as emit_mock,
        ):
            with self.assertRaises(RuntimeError):
                await gocryptfs_init("master-password")

        emit_mock.assert_not_awaited()
