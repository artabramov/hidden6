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

# NOTE (ADR-15): SQLite database lives on the gocryptfs mountpoint.
# With journal_mode=DELETE and synchronous=FULL a corrupted database is
# not expected. integrity_check still runs on every mount as a safety
# net: if the file is somehow damaged, the mount is rolled back instead
# of serving over a broken database.


async def check_db_integrity(db_path: str) -> None:
    """
    Run PRAGMA integrity_check on the database file.

    Raises RuntimeError if the database is corrupted so that the mount
    is rolled back and the operator is alerted early rather than allowing
    silent data corruption to propagate.
    """
    await asyncio.to_thread(_check_db_integrity_sync, db_path)
