# app/db/integrity.py
# SPDX-License-Identifier: GPL-3.0-only

import asyncio
import sqlite3


def _check_db_integrity_sync(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("PRAGMA integrity_check").fetchall()
    finally:
        conn.close()

    messages = [row[0] for row in rows]
    if messages != ["ok"]:
        raise RuntimeError(
            "SQLite integrity check failed: " + "; ".join(messages)
        )


# NOTE (ADR-17): SQLite database integrity is enforced on every mount.
# Database integrity is checked on every mount. The configured SQLite
# settings are expected to prevent corruption, but integrity_check is
# still required before the mount succeeds. Otherwise, the mount is
# rolled back instead of exposing a corrupted database.

async def check_db_integrity(db_path: str) -> None:
    """
    Run PRAGMA integrity_check on the database file.

    Raises RuntimeError if the database is corrupted so that the mount
    is rolled back and the operator is alerted early rather than allowing
    silent data corruption to propagate.
    """
    await asyncio.to_thread(_check_db_integrity_sync, db_path)
