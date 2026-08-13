# app/services/gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.errors import UnauthorizedError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.io import read
from app.runtime.cipherdir import cipherdir_unmount
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
    log.info("msg=gocryptfs_unmount_started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE,
    ):
        passphrase_encrypted = await read(config.GOCRYPTFS_PASSPHRASE_PATH)

        try:
            decrypt_passphrase(
                passphrase_encrypted,
                master_password.encode("utf-8"),
            )

        except ValueError:
            log.warning("msg=passphrase_invalid")
            raise UnauthorizedError

        # dispose() closes pooled connections before unmounting so the
        # running process does not retain file descriptors referencing
        # the gocryptfs mountpoint. This is process hygiene, not a
        # durability guarantee.

        from app.db.engine import engine  # noqa: PLC0415
        engine.sync_engine.dispose()

        await cipherdir_unmount(mountpoint=config.INSTALL_MOUNTPOINT)

    log.info("msg=gocryptfs_unmounted")
    await hooks.emit(Events.GOCRYPTFS_UNMOUNTED)
