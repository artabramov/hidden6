# tests/db/test_schema.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.db.schema import create_all_tables  # noqa: E402


class TestCreateAllTables(unittest.IsolatedAsyncioTestCase):

    async def test_loads_models_and_runs_create_all(self):
        conn = MagicMock()
        conn.run_sync = AsyncMock()

        begin_cm = MagicMock()
        begin_cm.__aenter__ = AsyncMock(return_value=conn)
        begin_cm.__aexit__ = AsyncMock(return_value=None)

        engine = MagicMock()
        engine.begin.return_value = begin_cm

        with (
            patch(
                "app.db.schema.load_all_models",
            ) as load_mock,
            patch(
                "app.db.schema.engine",
                engine,
            ),
        ):
            await create_all_tables()

        load_mock.assert_called_once_with()
        engine.begin.assert_called_once_with()
        conn.run_sync.assert_awaited_once_with(Base.metadata.create_all)
