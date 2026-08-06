# tests/helpers.py
# SPDX-License-Identifier: GPL-3.0-only

import os


def build_default_config_values() -> dict[str, object]:
    return {
        "INSTALL_SOURCE_CODE": "/opt/hidden",
        "INSTALL_CIPHERDIR": "/var/lib/cipherdir",
        "INSTALL_MOUNTPOINT": "/var/lib/mountpoint",
        "INSTALL_SECRETS": "/var/lib/secrets",
        "UVICORN_HOST": "127.0.0.1",
        "UVICORN_PORT": 80,
        "API_PREFIX": "/api/v1",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": (
            "%(asctime)s %(levelname)s %(name)s:%(lineno)d "
            "request_uuid=%(request_uuid)s %(message)s"
        ),
        "CORS_ALLOW_ORIGINS": (
            "http://localhost:3000,http://127.0.0.1:3000"
        ),
        "CORS_MAX_AGE_SECONDS": 86400,
        "EXTENSIONS_ENABLED": "",
        "SQLITE_JOURNAL_MODE": "DELETE",
        "SQLITE_SYNCHRONOUS": "FULL",
        "SQLITE_BUSY_TIMEOUT": 5000,
        "SQLITE_TEMP_STORE": "MEMORY",
        "SQLITE_FILENAME": "hidden.db",
    }


def set_minimal_app_config_env() -> None:
    for key, value in build_default_config_values().items():
        os.environ.setdefault(key, str(value))
