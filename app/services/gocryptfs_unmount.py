# app/services/gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.errors import (
    UnauthorizedError,
    ResourceConflictError,
    ServiceUnavailableError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.file import isfile, ismount, read
from app.runtime.cipherdir import is_cipherdir_created, cipherdir_unmount
from app.security.encryption import decrypt_passphrase

log = logging.getLogger(__name__)


async def gocryptfs_unmount(
    master_password: str,
) -> None:
    """
    Unmount the encrypted storage by verifying the master password
    against the stored passphrase and unmounting the gocryptfs
    filesystem.
    """
    log.info("msg=%s", "gocryptfs_unmount:started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE,
    ):
        if not await is_cipherdir_created(config.INSTALL_CIPHERDIR):
            log.warning("msg=%s", "gocryptfs_unmount:cipherdir_not_created")
            raise ServiceUnavailableError

        if not await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
            log.warning("msg=%s", "gocryptfs_unmount:passphrase_not_found")
            raise ServiceUnavailableError

        if not await ismount(config.INSTALL_MOUNTPOINT):
            log.warning("msg=%s", "gocryptfs_unmount:already_unmounted")
            raise ResourceConflictError

        passphrase_encrypted = await read(config.GOCRYPTFS_PASSPHRASE_PATH)
        try:
            decrypt_passphrase(
                passphrase_encrypted,
                master_password.encode("utf-8"),
            )

        except ValueError:
            log.warning("msg=%s", "gocryptfs_unmount:passphrase_invalid")
            raise UnauthorizedError

        # NOTE (ADR-XX): Dispose connections before gocryptfs unmount.
        # SQLite writes may still be buffered through the FUSE layer
        # even after transactions are committed. Unmounting with active
        # SQLAlchemy connections can leave partially flushed SQLite
        # pages and corrupt the database on the next mount. dispose()
        # prevents new writes from being issued through the old mount
        # before the encrypted filesystem is torn down.

        from app.db.engine import engine  # noqa: PLC0415
        engine.sync_engine.dispose()

        await cipherdir_unmount(mountpoint=config.INSTALL_MOUNTPOINT)

        log.info("msg=%s", "gocryptfs_unmount:completed")
        await hooks.emit(Events.GOCRYPTFS_UNMOUNT_COMPLETED)
