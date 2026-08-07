# extensions/example_extension/__init__.py
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from app.hooks import Events, HookManager


async def gocryptfs_inited(_: None) -> None:
    ...


async def gocryptfs_mounted(_: None) -> None:
    ...


async def gocryptfs_unmounted(_: None) -> None:
    ...


async def gocryptfs_rotated(_: None) -> None:
    ...


def register(hook_manager: HookManager) -> None:
    hook_manager.on(Events.GOCRYPTFS_INITED, gocryptfs_inited)
    hook_manager.on(Events.GOCRYPTFS_MOUNTED, gocryptfs_mounted)
    hook_manager.on(Events.GOCRYPTFS_UNMOUNTED, gocryptfs_unmounted)
    hook_manager.on(Events.GOCRYPTFS_ROTATED, gocryptfs_rotated)
