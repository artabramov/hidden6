# extensions/example_extension/__init__.py
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from app.hooks import Events, HookManager


async def gocryptfs_init_completed(obj: Any) -> None:
    ...


def register(hook_manager: HookManager) -> None:
    hook_manager.on(Events.GOCRYPTFS_INIT_COMPLETED, gocryptfs_init_completed)
