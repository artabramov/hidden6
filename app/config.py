# app/config.py
# SPDX-License-Identifier: GPL-3.0-only

import os
from functools import cached_property, lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    GOCRYPTFS_PASSPHRASE_FILENAME,
    FERNET_KEY_FILENAME,
)


class Config(BaseSettings):
    """
    Runtime configuration loaded from environment variables,
    plus computed filesystem paths derived from those values.
    """

    INSTALL_SOURCE_CODE_DIR: str
    INSTALL_CIPHERDIR_VOLUME_DIR: str
    INSTALL_MOUNTPOINT_DIR: str
    INSTALL_SECRETS_VOLUME_DIR: str
    UVICORN_HOST: str
    UVICORN_PORT: int
    API_PREFIX: str

    @cached_property
    def GOCRYPTFS_PASSPHRASE_PATH(self) -> str:
        return os.path.join(
            self.INSTALL_SECRETS_VOLUME_DIR,
            GOCRYPTFS_PASSPHRASE_FILENAME,
        )

    @cached_property
    def FERNET_KEY_PATH(self) -> str:
        return os.path.join(
            self.INSTALL_SECRETS_VOLUME_DIR,
            FERNET_KEY_FILENAME,
        )

    @cached_property
    def FERNET_KEY(self) -> str:
        """
        Return the Fernet key loaded from the configured file path.
        The value is loaded lazily and cached after the first access.
        """
        with open(self.FERNET_KEY_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()

    model_config = SettingsConfigDict(
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
