# tests/db/test_integrity.py
# SPDX-License-Identifier: GPL-3.0-only

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.db.integrity import (
    _check_db_integrity_sync,
    check_db_integrity,
)


class TestCheckDbIntegrity(unittest.IsolatedAsyncioTestCase):
    def test_passes_for_valid_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "hidden.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()

            _check_db_integrity_sync(db_path)

    def test_raises_when_integrity_check_fails(self):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("malformed",),
        ]

        with patch(
            "app.db.integrity.sqlite3.connect",
            return_value=mock_conn,
        ):
            with self.assertRaises(RuntimeError) as ctx:
                _check_db_integrity_sync("/any/path")

            self.assertIn("integrity check failed", str(ctx.exception))
        mock_conn.close.assert_called_once()

    async def test_async_wrapper_calls_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "hidden.db")
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            conn.commit()
            conn.close()

            await check_db_integrity(db_path)
