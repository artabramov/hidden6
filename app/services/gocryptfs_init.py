# app/services/gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from app.config import get_config
from app.constants import GOCRYPTFS_PASSPHRASE_LENGTH
from app.errors import ResourceConflictError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.file import delete, isfile, write
from app.security.encryption import encrypt_passphrase, generate_fernet_key
from app.security.randoms import generate_random_string
from app.runtime.cipherdir import is_cipherdir_created, cipherdir_create

log = logging.getLogger(__name__)

# NOTE (ADR-08): Cipherdir initialization uses best-effort rollback.
# The service creates the gocryptfs filesystem and all related secrets
# together. The operation is not transactional, so on failure the
# service performs best-effort cleanup of artifacts created during
# the current attempt.


async def gocryptfs_init(master_password: str) -> None:
    """
    Initialize encrypted storage by generating and encrypting a random
    gocryptfs passphrase, initializing the cipherdir, creating the
    internal application keys, and persisting all created secrets.
    """
    log.info("msg=%s", "gocryptfs_init:started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE
    ):

        if await is_cipherdir_created(config.INSTALL_CIPHERDIR):
            log.warning("msg=%s", "gocryptfs_init:cihperdir_created")
            raise ResourceConflictError

        if await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
            log.warning("msg=%s", "gocryptfs_init:passphrase_exists")
            raise ResourceConflictError

        if await isfile(config.FERNET_ENCRYPTION_KEY_PATH):
            log.warning("msg=%s", "gocryptfs_init:fernet_key_exists")
            raise ResourceConflictError

        passphrase = generate_random_string(GOCRYPTFS_PASSPHRASE_LENGTH)
        passphrase_encrypted = encrypt_passphrase(
            passphrase.encode("utf-8"),
            master_password.encode("utf-8"),
        )

        fernet_key = generate_fernet_key()

        try:
            await write(
                config.GOCRYPTFS_PASSPHRASE_PATH,
                passphrase_encrypted,
            )

            await cipherdir_create(
                passphrase,
                config.INSTALL_CIPHERDIR
            )

            await write(
                config.FERNET_ENCRYPTION_KEY_PATH,
                fernet_key.encode("utf-8")
            )

        except Exception:
            await delete(config.GOCRYPTFS_PASSPHRASE_PATH)
            await delete(os.path.join(
                config.INSTALL_CIPHERDIR,
                "gocryptfs.conf"
            ))
            await delete(os.path.join(
                config.INSTALL_CIPHERDIR,
                "gocryptfs.diriv"
            ))
            await delete(config.FERNET_ENCRYPTION_KEY_PATH)

            log.exception("msg=%s", "gocryptfs_init:failed")
            raise

        log.info("msg=%s", "gocryptfs_init:completed")
        await hooks.emit(Events.GOCRYPTFS_INITED)
