# tests/test_hooks.py
# SPDX-License-Identifier: GPL-3.0-only

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.hooks import Events, HookManager


class TestHookManagerEmit(unittest.IsolatedAsyncioTestCase):
    async def test_executes_registered_hooks_in_order(self):
        manager = HookManager()
        calls: list[str] = []

        async def first(_obj):
            calls.append("first")

        async def second(_obj):
            calls.append("second")

        manager.on(Events.GOCRYPTFS_INITED, first)
        manager.on(Events.GOCRYPTFS_INITED, second)

        await manager.emit(Events.GOCRYPTFS_INITED)

        self.assertEqual(calls, ["first", "second"])

    async def test_passes_obj_to_hook(self):
        manager = HookManager()
        received: list[object] = []

        async def capture(obj):
            received.append(obj)

        manager.on(Events.GOCRYPTFS_INITED, capture)

        payload = {"id": 1}
        await manager.emit(Events.GOCRYPTFS_INITED, payload)

        self.assertEqual(received, [payload])

    async def test_no_hooks_is_noop(self):
        manager = HookManager()

        await manager.emit(Events.GOCRYPTFS_INITED)

    async def test_hook_failure_is_logged_and_does_not_stop_others(self):
        manager = HookManager()
        calls: list[str] = []

        async def failing(_obj):
            raise RuntimeError("boom")

        async def succeeding(_obj):
            calls.append("ok")

        manager.on(Events.GOCRYPTFS_INITED, failing)
        manager.on(Events.GOCRYPTFS_INITED, succeeding)

        with patch("app.hooks.logger") as mock_logger:
            await manager.emit(Events.GOCRYPTFS_INITED)

        self.assertEqual(calls, ["ok"])
        mock_logger.exception.assert_called_once()


class TestHookManagerLoadExtensions(unittest.TestCase):
    def setUp(self):
        self.manager = HookManager()

    def test_loads_configured_extension(self):
        config = MagicMock()
        config.EXTENSIONS_ENABLED = "example_extension"

        with patch(
            "app.hooks.get_config",
            return_value=config,
        ):
            self.manager.load_extensions()

        self.assertTrue(self.manager._loaded)
        self.assertEqual(
            len(self.manager._hooks[Events.GOCRYPTFS_INITED]),
            1,
        )

    def test_splits_and_strips_csv_extensions(self):
        config = MagicMock()
        config.EXTENSIONS_ENABLED = " example_extension , "

        with (
            patch(
                "app.hooks.get_config",
                return_value=config,
            ),
            patch(
                "app.hooks.importlib.import_module",
            ) as import_mock,
        ):
            self.manager.load_extensions()

        import_mock.assert_called_once_with(
            "extensions.example_extension",
        )

    def test_empty_extensions_loads_nothing(self):
        config = MagicMock()
        config.EXTENSIONS_ENABLED = ""

        with (
            patch(
                "app.hooks.get_config",
                return_value=config,
            ),
            patch(
                "app.hooks.importlib.import_module",
            ) as import_mock,
        ):
            self.manager.load_extensions()

        import_mock.assert_not_called()
        self.assertTrue(self.manager._loaded)

    def test_loads_only_once(self):
        config = MagicMock()
        config.EXTENSIONS_ENABLED = "example_extension"

        with (
            patch(
                "app.hooks.get_config",
                return_value=config,
            ),
            patch(
                "app.hooks.importlib.import_module",
            ) as import_mock,
        ):
            self.manager.load_extensions()
            self.manager.load_extensions()

        import_mock.assert_called_once()

    def test_skips_extension_without_register(self):
        config = MagicMock()
        config.EXTENSIONS_ENABLED = "broken_extension"

        broken_extension = SimpleNamespace()
        real_import_module = importlib.import_module

        def fake_import_module(name, package=None):
            if name == "extensions.broken_extension":
                return broken_extension
            return real_import_module(name, package)

        with (
            patch(
                "app.hooks.get_config",
                return_value=config,
            ),
            patch(
                "app.hooks.importlib.import_module",
                side_effect=fake_import_module,
            ),
            patch("app.hooks.logger") as mock_logger,
        ):
            self.manager.load_extensions()

        mock_logger.warning.assert_called_once()
        self.assertEqual(
            self.manager._hooks[Events.GOCRYPTFS_INITED],
            [],
        )
