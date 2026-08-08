# app/db/schema.py
# SPDX-License-Identifier: GPL-3.0-only

from app.db.base import Base
from app.db.engine import engine, load_all_models


async def create_all_tables() -> None:
    """
    Create all ORM tables in the mounted SQLite database.

    Idempotent: existing tables are left unchanged. Used on mount until
    Alembic migrations replace this bootstrap path.
    """
    load_all_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
