# app/services/gocryptfs_mount.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.db.integrity import check_db_integrity
from app.errors import (
    BadRequestError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.file import isdir, isfile, ismount, mkdir, read
from app.runtime.cipherdir import (
    is_cipherdir_created,
    cipherdir_mount,
    cipherdir_unmount,
)
from app.security.encryption import decrypt_passphrase

log = logging.getLogger(__name__)


# TODO: Add garbage cleaning (removal of possible file system artifacts)
# when cipherdir mounting.

async def gocryptfs_mount(master_password: str) -> None:
    """
    Mount the encrypted storage by decrypting the stored passphrase
    with the master password, mounting the gocryptfs filesystem,
    ensuring mountpoint directories exist (db, buckets, versions, tmp),
    and initializing the database. If a post-mount step fails, the
    mount is rolled back.
    """
    log.info("msg=%s", "gocryptfs_mount:started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE,
    ):

        if not await is_cipherdir_created(config.INSTALL_CIPHERDIR):
            log.warning("msg=%s", "gocryptfs_mount:not_created")
            raise ResourceNotFoundError

        if not await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
            log.warning("msg=%s", "gocryptfs_mount:passphrase_not_found")
            raise ResourceNotFoundError

        if await ismount(config.INSTALL_MOUNTPOINT):
            log.warning("msg=%s", "gocryptfs_mount:already_mounted")
            raise ResourceConflictError

        passphrase_encrypted = await read(config.GOCRYPTFS_PASSPHRASE_PATH)
        try:
            passphrase_bytes = decrypt_passphrase(
                passphrase_encrypted,
                master_password.encode("utf-8"),
            )

        except ValueError:
            log.warning("msg=%s", "gocryptfs_mount:passphrase_invalid")
            raise BadRequestError

        if not await isdir(config.INSTALL_MOUNTPOINT):
            await mkdir(config.INSTALL_MOUNTPOINT)

        await cipherdir_mount(
            passphrase=passphrase_bytes.decode("utf-8"),
            cipherdir=config.INSTALL_CIPHERDIR,
            mountpoint=config.INSTALL_MOUNTPOINT,
        )

        try:
            if not await isdir(config.MOUNTPOINT_DB_DIR):
                await mkdir(config.MOUNTPOINT_DB_DIR)

            if not await isdir(config.MOUNTPOINT_BUCKETS_DIR):
                await mkdir(config.MOUNTPOINT_BUCKETS_DIR)

            if not await isdir(config.MOUNTPOINT_VERSIONS_DIR):
                await mkdir(config.MOUNTPOINT_VERSIONS_DIR)

            if not await isdir(config.MOUNTPOINT_TMP_DIR):
                await mkdir(config.MOUNTPOINT_TMP_DIR)

            # await upgrade_db()
            await check_db_integrity(config.SQLITE_PATH)

        except Exception:
            log.exception("msg=%s", "gocryptfs_mount:failed")

            try:
                await cipherdir_unmount(config.INSTALL_MOUNTPOINT)
                log.warning("msg=%s", "gocryptfs_mount:rollback_completed")

            except Exception:
                log.exception("msg=%s", "gocryptfs_mount:rollback_failed")

            raise

        log.info("msg=%s", "gocryptfs_mount:completed")
        await hooks.emit(Events.GOCRYPTFS_MOUNT_COMPLETED)
