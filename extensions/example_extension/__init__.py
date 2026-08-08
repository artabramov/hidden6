# extensions/example_extension/__init__.py
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from app.db.engine import SessionLocal
from app.hooks import Events, HookManager
from app.repositories.orm import ORMRepository
from app.models.user import User
from app.models.user_key import UserKey


async def gocryptfs_inited(_: None) -> None:
    ...


async def gocryptfs_mounted(_: None) -> None:
    ...


async def gocryptfs_unmounted(_: None) -> None:
    ...


async def gocryptfs_rotated(_: None) -> None:
    ...


async def gocryptfs_revealed(_: None) -> None:
    ...


async def user_root_create(user: User) -> None:
    async with SessionLocal() as session:
        repo = ORMRepository(session)
        keys = await repo.select_all(UserKey, user_id=user.id)
        a = 1
    ...


def register(hook_manager: HookManager) -> None:
    hook_manager.on(Events.GOCRYPTFS_INITED, gocryptfs_inited)
    hook_manager.on(Events.GOCRYPTFS_MOUNTED, gocryptfs_mounted)
    hook_manager.on(Events.GOCRYPTFS_UNMOUNTED, gocryptfs_unmounted)
    hook_manager.on(Events.GOCRYPTFS_ROTATED, gocryptfs_rotated)
    hook_manager.on(Events.GOCRYPTFS_REVEALED, gocryptfs_revealed)
    hook_manager.on(Events.USER_ROOT_CREATED, user_root_create)
