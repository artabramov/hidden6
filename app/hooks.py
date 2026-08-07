# app/hooks.py
# SPDX-License-Identifier: GPL-3.0-only

import importlib
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from app.config import get_config

log = logging.getLogger(__name__)

Hook = Callable[[Any], Awaitable[Any]]


class Events:
    """
    Hook event identifiers. Used exclusively as keys for hook
    registration and emission, not for logging.
    """
    GOCRYPTFS_INITED = "gocryptfs_inited"
    GOCRYPTFS_MOUNTED = "gocryptfs_mounted"
    GOCRYPTFS_UNMOUNTED = "gocryptfs_unmounted"
    GOCRYPTFS_ROTATED = "gocryptfs_rotated"
    GOCRYPTFS_REVEALED = "gocryptfs_revealed"


class HookManager:
    """
    Registers and emits hooks for named events. Loads hook registrations
    from configured extensions and executes them sequentially after the
    main operation has completed. Hook failures are logged and do not
    interrupt other hooks.
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[Hook]] = defaultdict(list)
        self._loaded = False

    def on(self, event: str, hook: Hook) -> None:
        """
        Register a hook for the specified event.
        Hooks are executed in registration order.
        """
        self._hooks[event].append(hook)

    async def emit(self, event: str, obj: Any = None) -> None:
        """
        Emit an event and execute all registered hooks.
        Exceptions are logged and do not interrupt execution.
        """
        for hook in self._hooks.get(event, []):
            try:
                await hook(obj)
            except Exception as exc:
                log.exception(
                    "msg=hook_failed event=%s error=%s",
                    event,
                    exc,
                )

    def load_extensions(self) -> None:
        """
        Load and register hooks from configured extensions.
        Ensures extensions are loaded only once.
        """
        if self._loaded:
            return

        config = get_config()
        extensions = [
            e.strip()
            for e in config.EXTENSIONS_ENABLED.split(",")
            if e.strip()
        ]

        for extension_name in extensions:
            module_name = f"extensions.{extension_name}"
            module = importlib.import_module(module_name)

            register = getattr(module, "register", None)
            if not callable(register):
                log.warning(
                    "msg=extension_skipped module=%s",
                    module_name,
                )
                continue

            register(self)
            log.info("msg=extension_loaded module=%s", module_name)

        self._loaded = True


hooks = HookManager()
