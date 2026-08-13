# app/services/gocryptfs_mount.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.db.integrity import check_db_integrity
from app.db.schema import create_all_tables
from app.errors import UnauthorizedError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.io import isdir, mktree, read
from app.runtime.cipherdir import cipherdir_mount, cipherdir_unmount
from app.security.encryption import decrypt_passphrase

log = logging.getLogger(__name__)


# TODO: Add garbage cleaning (removal of possible file system artifacts)
# when cipherdir mounting.

async def gocryptfs_mount(master_password: str) -> None:
    """
    Mount the encrypted storage by decrypting the stored passphrase
    with the master password, mounting the gocryptfs filesystem,
    ensuring mountpoint directories exist (db, buckets, tmp),
    creating ORM tables if missing, and checking database integrity.
    If a post-mount step fails, the mount is rolled back.
    """
    log.info("msg=gocryptfs_mount_started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE,
    ):
        passphrase_encrypted = await read(config.GOCRYPTFS_PASSPHRASE_PATH)

        try:
            passphrase_bytes = decrypt_passphrase(
                passphrase_encrypted,
                master_password.encode("utf-8"),
            )

        except ValueError:
            log.warning("msg=passphrase_invalid")
            raise UnauthorizedError

        if not await isdir(config.INSTALL_MOUNTPOINT):
            await mktree(config.INSTALL_MOUNTPOINT)

        await cipherdir_mount(
            passphrase=passphrase_bytes.decode("utf-8"),
            cipherdir=config.INSTALL_CIPHERDIR,
            mountpoint=config.INSTALL_MOUNTPOINT,
        )

        try:
            if not await isdir(config.MOUNTPOINT_DB_DIR):
                await mktree(config.MOUNTPOINT_DB_DIR)

            if not await isdir(config.MOUNTPOINT_BUCKETS_DIR):
                await mktree(config.MOUNTPOINT_BUCKETS_DIR)

            if not await isdir(config.MOUNTPOINT_TMP_DIR):
                await mktree(config.MOUNTPOINT_TMP_DIR)

            await create_all_tables()
            await check_db_integrity(config.SQLITE_PATH)

        except Exception:
            log.exception("msg=gocryptfs_mount_failed")

            try:
                await cipherdir_unmount(config.INSTALL_MOUNTPOINT)
                log.warning("msg=rollback_completed")

            except Exception:
                log.exception("msg=rollback_failed")

            raise

    log.info("msg=gocryptfs_mounted")
    await hooks.emit(Events.GOCRYPTFS_MOUNTED)
