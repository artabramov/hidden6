# app/config.py
# SPDX-License-Identifier: GPL-3.0-only

import os
from functools import cached_property, lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import (
    GOCRYPTFS_PASSPHRASE_FILENAME,
    FERNET_ENCRYPTION_KEY_FILENAME,
    MOUNTPOINT_DB_DIRNAME,
    MOUNTPOINT_BUCKETS_DIRNAME,
    MOUNTPOINT_VERSIONS_DIRNAME,
    MOUNTPOINT_TMP_DIRNAME,
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
    LOG_LEVEL: str
    LOG_FORMAT: str
    CORS_ALLOW_ORIGINS: str
    CORS_MAX_AGE_SECONDS: int
    SQLITE_JOURNAL_MODE: str
    SQLITE_SYNCHRONOUS: str
    SQLITE_BUSY_TIMEOUT: int
    SQLITE_TEMP_STORE: str
    SQLITE_FILENAME: str
    EXTENSIONS_ENABLED: str = ""

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
    def MOUNTPOINT_DB_DIR(self) -> str:
        return os.path.join(
            self.INSTALL_MOUNTPOINT,
            MOUNTPOINT_DB_DIRNAME,
        )

    @cached_property
    def MOUNTPOINT_BUCKETS_DIR(self) -> str:
        return os.path.join(
            self.INSTALL_MOUNTPOINT,
            MOUNTPOINT_BUCKETS_DIRNAME,
        )

    @cached_property
    def MOUNTPOINT_VERSIONS_DIR(self) -> str:
        return os.path.join(
            self.INSTALL_MOUNTPOINT,
            MOUNTPOINT_VERSIONS_DIRNAME,
        )

    @cached_property
    def MOUNTPOINT_TMP_DIR(self) -> str:
        return os.path.join(
            self.INSTALL_MOUNTPOINT,
            MOUNTPOINT_TMP_DIRNAME,
        )

    @cached_property
    def SQLITE_PATH(self) -> str:
        return os.path.join(
            self.MOUNTPOINT_DB_DIR,
            self.SQLITE_FILENAME,
        )

    @cached_property
    def SQLITE_URL(self) -> str:
        return "sqlite+aiosqlite:///" + self.SQLITE_PATH

    model_config = SettingsConfigDict(
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
