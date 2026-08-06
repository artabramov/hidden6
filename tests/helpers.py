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
    }


def set_minimal_app_config_env() -> None:
    for key, value in build_default_config_values().items():
        os.environ.setdefault(key, str(value))
