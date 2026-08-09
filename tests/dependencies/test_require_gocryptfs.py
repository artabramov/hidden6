# tests/dependencies/test_require_gocryptfs.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.dependencies.require_gocryptfs import require_gocryptfs  # noqa: E402
from app.errors import (  # noqa: E402
    BadGatewayError,
    ServiceUnavailableError,
)


class TestRequireGocryptfs(unittest.IsolatedAsyncioTestCase):
    def _build_config(self):
        config = MagicMock()
        config.INSTALL_CIPHERDIR = "/fake/cipherdir"
        config.INSTALL_MOUNTPOINT = "/fake/mountpoint"
        config.GOCRYPTFS_PASSPHRASE_PATH = "/fake/secrets/passphrase.enc"
        return config

    async def test_passes_when_all_required_resources_exist(self):
        config = self._build_config()
        check = require_gocryptfs()

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ) as cipherdir_mock,
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(return_value=True),
            ) as ismount_mock,
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(return_value=True),
            ) as isfile_mock,
        ):
            await check()

        cipherdir_mock.assert_awaited_once_with(config.INSTALL_CIPHERDIR)
        ismount_mock.assert_awaited_once_with(config.INSTALL_MOUNTPOINT)
        isfile_mock.assert_awaited_once_with(
            config.GOCRYPTFS_PASSPHRASE_PATH,
        )

    async def test_raises_503_when_cipherdir_missing(self):
        config = self._build_config()
        check = require_gocryptfs()

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(),
            ) as ismount_mock,
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
        ):
            with self.assertRaises(ServiceUnavailableError):
                await check()

        ismount_mock.assert_not_awaited()
        isfile_mock.assert_not_awaited()

    async def test_raises_503_when_mountpoint_missing(self):
        config = self._build_config()
        check = require_gocryptfs()

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
        ):
            with self.assertRaises(ServiceUnavailableError):
                await check()

        isfile_mock.assert_not_awaited()

    async def test_raises_503_when_passphrase_missing(self):
        config = self._build_config()
        check = require_gocryptfs()

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(return_value=False),
            ),
        ):
            with self.assertRaises(ServiceUnavailableError):
                await check()

    async def test_raises_502_when_cipherdir_exists_but_forbidden(self):
        config = self._build_config()
        check = require_gocryptfs(
            require_cipherdir=False,
            require_mountpoint=False,
            require_passphrase=False,
        )

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(),
            ) as ismount_mock,
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
        ):
            with self.assertRaises(BadGatewayError):
                await check()

        ismount_mock.assert_not_awaited()
        isfile_mock.assert_not_awaited()

    async def test_raises_502_when_mountpoint_exists_but_forbidden(self):
        config = self._build_config()
        check = require_gocryptfs(
            require_cipherdir=False,
            require_mountpoint=False,
            require_passphrase=False,
        )

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(),
            ) as isfile_mock,
        ):
            with self.assertRaises(BadGatewayError):
                await check()

        isfile_mock.assert_not_awaited()

    async def test_raises_502_when_passphrase_exists_but_forbidden(self):
        config = self._build_config()
        check = require_gocryptfs(
            require_cipherdir=False,
            require_mountpoint=False,
            require_passphrase=False,
        )

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(return_value=True),
            ),
        ):
            with self.assertRaises(BadGatewayError):
                await check()

    async def test_passes_when_all_resources_absent_and_forbidden(self):
        config = self._build_config()
        check = require_gocryptfs(
            require_cipherdir=False,
            require_mountpoint=False,
            require_passphrase=False,
        )

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=False),
            ) as cipherdir_mock,
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(return_value=False),
            ) as ismount_mock,
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(return_value=False),
            ) as isfile_mock,
        ):
            await check()

        cipherdir_mock.assert_awaited_once()
        ismount_mock.assert_awaited_once()
        isfile_mock.assert_awaited_once()

    async def test_mixed_flags_require_cipherdir_forbid_mount(self):
        config = self._build_config()
        check = require_gocryptfs(
            require_cipherdir=True,
            require_mountpoint=False,
            require_passphrase=True,
        )

        with (
            patch(
                "app.dependencies.require_gocryptfs.get_config",
                return_value=config,
            ),
            patch(
                "app.dependencies.require_gocryptfs.is_cipherdir_created",
                new=AsyncMock(return_value=True),
            ),
            patch(
                "app.dependencies.require_gocryptfs.ismount",
                new=AsyncMock(return_value=False),
            ),
            patch(
                "app.dependencies.require_gocryptfs.isfile",
                new=AsyncMock(return_value=True),
            ),
        ):
            await check()
