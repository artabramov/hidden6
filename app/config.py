# app/config.py
# SPDX-License-Identifier: GPL-3.0-only

import os
from functools import cached_property, lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    GOCRYPTFS_PASSPHRASE_FILENAME,
    FERNET_ENCRYPTION_KEY_FILENAME,
    TMP_DIRNAME,
)


class Config(BaseSettings):
    """
    Centralized runtime configuration.

    Combines environment variables, application constants,
    and derived values into a single configuration object.
    """

    INSTALL_SOURCE_CODE: str
    INSTALL_CIPHERDIR: str
    INSTALL_MOUNTPOINT: str
    INSTALL_SECRETS: str
    UVICORN_HOST: str
    UVICORN_PORT: int
    API_PREFIX: str

    @cached_property
    def GOCRYPTFS_PASSPHRASE_PATH(self) -> str:
        return os.path.join(
            self.INSTALL_SECRETS,
            GOCRYPTFS_PASSPHRASE_FILENAME,
        )

    @cached_property
    def FERNET_ENCRYPTION_KEY_PATH(self) -> str:
        return os.path.join(
            self.INSTALL_SECRETS,
            FERNET_ENCRYPTION_KEY_FILENAME,
        )

    @cached_property
    def TMP_DIR(self) -> str:
        return os.path.join(
            self.GOCRYPTFS_MOUNTPOINT,
            TMP_DIRNAME,
        )

    model_config = SettingsConfigDict(
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
