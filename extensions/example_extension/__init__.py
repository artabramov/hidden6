# extensions/example_extension/__init__.py
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations
from typing import List

from app.db.engine import SessionLocal
from app.hooks import Events, HookManager
from app.repositories.orm import ORMRepository
from app.models.user import User
from app.models.user_key import UserKey
from app.models.bucket import Bucket
from app.models.objekt import Objekt


async def gocryptfs_initialized(_: None) -> None:
    ...


async def gocryptfs_mounted(_: None) -> None:
    ...


async def gocryptfs_unmounted(_: None) -> None:
    ...


async def gocryptfs_rotated(_: None) -> None:
    ...


async def gocryptfs_revealed(_: None) -> None:
    ...


async def user_initialized(user: User) -> None:
    async with SessionLocal() as session:
        repo = ORMRepository(session)
        user_keys = await repo.select_all(  # noqa: F841
            UserKey,
            user_id=user.id
        )
    ...


async def bucket_created(bucket: Bucket) -> None:
    ...


async def bucket_listed(buckets: List[Bucket]) -> None:
    ...


async def objekt_uploaded(objekt: Objekt) -> None:
    ...


async def objekt_listed(objekts: List[Objekt]) -> None:
    ...


def register(hook_manager: HookManager) -> None:
    hook_manager.on(Events.GOCRYPTFS_INITIALIZED, gocryptfs_initialized)
    hook_manager.on(Events.GOCRYPTFS_MOUNTED, gocryptfs_mounted)
    hook_manager.on(Events.GOCRYPTFS_UNMOUNTED, gocryptfs_unmounted)
    hook_manager.on(Events.GOCRYPTFS_ROTATED, gocryptfs_rotated)
    hook_manager.on(Events.GOCRYPTFS_REVEALED, gocryptfs_revealed)
    hook_manager.on(Events.USER_INITIALIZED, user_initialized)
    hook_manager.on(Events.BUCKET_CREATED, bucket_created)
    hook_manager.on(Events.BUCKET_LISTED, bucket_listed)
    hook_manager.on(Events.OBJEKT_UPLOADED, objekt_uploaded)
    hook_manager.on(Events.OBJEKT_LISTED, objekt_listed)
