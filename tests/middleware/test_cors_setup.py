# tests/middleware/test_cors_setup.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock, patch

from fastapi.middleware.cors import CORSMiddleware

from app.middleware.cors_setup import cors_setup_middleware


class TestCorsSetupMiddleware(unittest.TestCase):
    def test_configures_cors_middleware_with_expected_options(self):
        app = MagicMock()
        config = MagicMock()
        config.CORS_ALLOW_ORIGINS = (
            "http://localhost:3000,http://localhost:5173"
        )
        config.CORS_MAX_AGE_SECONDS = 86400

        with patch(
            "app.middleware.cors_setup.get_config",
            return_value=config,
        ):
            cors_setup_middleware(app)

        app.add_middleware.assert_called_once_with(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://localhost:5173",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            max_age=config.CORS_MAX_AGE_SECONDS,
        )

    def test_splits_and_strips_csv_origins(self):
        app = MagicMock()
        config = MagicMock()
        config.CORS_ALLOW_ORIGINS = " http://a , ,http://b "
        config.CORS_MAX_AGE_SECONDS = 60

        with patch(
            "app.middleware.cors_setup.get_config",
            return_value=config,
        ):
            cors_setup_middleware(app)

        allow_origins = app.add_middleware.call_args.kwargs[
            "allow_origins"
        ]
        self.assertEqual(allow_origins, ["http://a", "http://b"])

    def test_empty_origins_become_empty_list(self):
        app = MagicMock()
        config = MagicMock()
        config.CORS_ALLOW_ORIGINS = ""
        config.CORS_MAX_AGE_SECONDS = 60

        with patch(
            "app.middleware.cors_setup.get_config",
            return_value=config,
        ):
            cors_setup_middleware(app)

        allow_origins = app.add_middleware.call_args.kwargs[
            "allow_origins"
        ]
        self.assertEqual(allow_origins, [])
