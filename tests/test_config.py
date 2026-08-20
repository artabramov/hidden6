# tests/test_config.py
# SPDX-License-Identifier: GPL-3.0-only

import os
import unittest

from tests.helpers import build_default_config_values, set_minimal_app_config_env


class TestConfigSqlitePaths(unittest.TestCase):
    def setUp(self):
        self._saved = {
            key: os.environ.get(key)
            for key in build_default_config_values()
        }
        for key in build_default_config_values():
            os.environ.pop(key, None)
        set_minimal_app_config_env()

        from app.config import get_config

        get_config.cache_clear()
        self.get_config = get_config

    def tearDown(self):
        from app.config import get_config

        get_config.cache_clear()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_sqlite_path_uses_mountpoint_db_dir_and_filename(self):
        config = self.get_config()

        self.assertEqual(
            config.SQLITE_PATH,
            "/var/lib/mountpoint/db/hidden.db",
        )
        self.assertEqual(
            config.SQLITE_URL,
            "sqlite+aiosqlite:////var/lib/mountpoint/db/hidden.db",
        )

    def test_mountpoint_dirs_are_derived_from_install_mountpoint(self):
        config = self.get_config()

        self.assertEqual(
            config.MOUNTPOINT_DB_DIR,
            "/var/lib/mountpoint/db",
        )
        self.assertEqual(
            config.MOUNTPOINT_BUCKETS_DIR,
            "/var/lib/mountpoint/buckets",
        )
        self.assertEqual(
            config.MOUNTPOINT_VERSIONS_DIR,
            "/var/lib/mountpoint/versions",
        )
        self.assertEqual(
            config.MOUNTPOINT_TMP_DIR,
            "/var/lib/mountpoint/tmp",
        )
