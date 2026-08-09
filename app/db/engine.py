# app/db/engine.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_config

config = get_config()


# NOTE (ADR-17): SQLite is configured for the gocryptfs-backed stack.
# The SQLite database resides inside the gocryptfs-encrypted storage.
# Client-server databases are not used because they cannot operate on
# the encrypted filesystem in this design. SQLite is configured with
# journal_mode=DELETE and synchronous=FULL, so database corruption is
# not expected. Critical points:
# 1. Journal mode MUST be DELETE (rollback journal).
#    WAL mode creates a shared-memory index file (.sqlite-shm). Its
#    read-decrypt-modify-encrypt-write cycle through gocryptfs is not
#    atomic. Combined with aiosqlite background-thread execution, this
#    deterministically corrupts the database.
# 2. Synchronous mode MUST be FULL.
#    FULL issues fsync() on every commit. NORMAL allows writes to remain
#    buffered by the FUSE layer, which can lose committed data if the
#    container stops before the buffers are flushed.

engine = create_async_engine(
    config.SQLITE_URL,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """
    Apply SQLite PRAGMA settings for each new database connection.
    These values are provided through the application configuration.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute(f"PRAGMA journal_mode={config.SQLITE_JOURNAL_MODE}")
    cursor.execute(f"PRAGMA synchronous={config.SQLITE_SYNCHRONOUS}")
    cursor.execute(f"PRAGMA busy_timeout={config.SQLITE_BUSY_TIMEOUT}")
    cursor.execute(f"PRAGMA temp_store={config.SQLITE_TEMP_STORE}")
    cursor.close()


# NOTE (ADR-19): SQLite ORM relationships do not use implicit loading.
# SQLAlchemy relationships use lazy="raise" instead of selectin or
# joined. Related rows are queried only when needed, avoiding extra
# SQLite queries in the single-worker runtime. Accidental attribute
# access fails fast instead of issuing a hidden query (or raising
# MissingGreenlet under AsyncSession).

def load_all_models() -> None:
    """
    Import all ORM models so SQLAlchemy can resolve relationships.
    """
    import app.models.user  # noqa: F401, PLC0415
    import app.models.user_key  # noqa: F401, PLC0415
    import app.models.user_policy  # noqa: F401, PLC0415
