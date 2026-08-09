# app/runtime/watchdog.py
# SPDX-License-Identifier: GPL-3.0-only

import asyncio
import logging
from pathlib import Path

from app.config import get_config
from app.constants import WATCHDOG_HEARTBEAT_PATH
from app.log import init_logging
from app.repositories.file import isdir, isfile, ismount
from app.runtime.cipherdir import cipherdir_unmount

log = logging.getLogger(__name__)

# NOTE (ADR-12): Watchdog performs an immediate emergency unmount.
# The mountpoint is detached using the -z flag. In-flight requests may
# fail with HTTP 500. Full handling of storage failures within request
# execution is intentionally avoided to keep runtime logic simple and
# predictable.


async def run_watchdog() -> None:
    """
    If the mountpoint is mounted, the watchdog triggers an emergency
    unmount when critical conditions are violated (missing secrets,
    missing passphrase, or application not running).
    """
    config = get_config()
    Path(WATCHDOG_HEARTBEAT_PATH).touch()

    if not await ismount(config.INSTALL_MOUNTPOINT):
        return

    if not await isdir(config.INSTALL_SECRETS):
        log.warning("msg=watchdog_secrets_missing")
        await cipherdir_unmount(config.INSTALL_MOUNTPOINT)
        log.info("msg=watchdog_unmount_completed")
        return

    if not await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
        log.warning("msg=watchdog_passphrase_missing")
        await cipherdir_unmount(config.INSTALL_MOUNTPOINT)
        log.info("msg=watchdog_unmount_completed")
        return

    if not _is_application_running():
        log.warning("msg=watchdog_application_missing")
        await cipherdir_unmount(config.INSTALL_MOUNTPOINT)
        log.info("msg=watchdog_unmount_completed")


def _is_application_running() -> bool:
    """
    Return whether a process matching the expected Uvicorn application
    command line is present in /proc.
    """
    proc_path = Path("/proc")

    try:
        entries = proc_path.iterdir()
    except OSError:
        return False

    for entry in entries:
        if not entry.name.isdigit():
            continue

        try:
            cmdline = (entry / "cmdline").read_bytes()
        except OSError:
            continue

        if not cmdline:
            continue

        if b"uvicorn" in cmdline and b"app.main:app" in cmdline:
            return True

    return False


if __name__ == "__main__":
    init_logging()
    raise SystemExit(asyncio.run(run_watchdog()))
