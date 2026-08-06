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


# NOTE (ADR-XX): SQLite is used as the database backend.
# The database file resides inside the gocryptfs-encrypted storage.
# Client-server databases are not used because they cannot operate on
# the encrypted filesystem in this design. Critical points:
# 1. Journal mode MUST be DELETE (rollback journal).
#    WAL mode creates a shared-memory index file (.sqlite-shm) whose
#    read-decrypt-modify-encrypt-write cycle through gocryptfs is not
#    atomic. aiosqlite executes SQLite in a background thread
#    concurrently with the asyncio event loop. This concurrency window,
#    combined with gocryptfs block-level encryption, causes deterministic
#    database corruption.
# 2. Synchronous mode MUST be FULL.
#    This ensures fsync() is issued on every commit. NORMAL allows writes
#    to remain buffered by the FUSE layer, which can result in data loss
#    if the container stops before buffered data is flushed.

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


def load_all_models() -> None:
    """
    Import all ORM models so SQLAlchemy can resolve relationships.
    """
    ...
