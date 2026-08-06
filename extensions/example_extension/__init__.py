# extensions/example_extension/__init__.py
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from app.hooks import Events, HookManager


async def init_gocryptfs(obj: None) -> None:
    ...


def register(hook_manager: HookManager) -> None:
    hook_manager.on(Events.GOCRYPTFS_INIT_COMPLETED, init_gocryptfs)
