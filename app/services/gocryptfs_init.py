# app/services/gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

import logging
import os

from app.config import get_config
from app.constants import GOCRYPTFS_PASSPHRASE_LENGTH
from app.errors import BadGatewayError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.file import delete, isfile, write
from app.security.encryption import encrypt_passphrase, generate_fernet_key
from app.security.randoms import generate_random_string
from app.runtime.cipherdir import cipherdir_create

log = logging.getLogger(__name__)


# NOTE (ADR-09): Gocryptfs passphrase is protected by master password.
# It is encrypted with a master password and is never persisted in
# plaintext on disk. The passphrase exists in plaintext only in memory
# during mount and is discarded immediately afterwards. Access to the
# encrypted data therefore requires both the passphrase and the master
# password.

async def gocryptfs_init(master_password: str) -> None:
    """
    Initialize encrypted storage by generating and encrypting a random
    gocryptfs passphrase, initializing the cipherdir, creating the
    internal application keys, and persisting all created secrets.

    Initialization is not transactional. If any step fails, the
    function performs best-effort cleanup of artifacts created during
    the current attempt.
    """
    log.info("msg=gocryptfs_initialization_started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE
    ):
        if await isfile(config.FERNET_ENCRYPTION_KEY_PATH):
            log.warning("msg=fernet_key_already_exists")
            raise BadGatewayError

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
            log.exception("msg=gocryptfs_initialization_failed")

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

            raise

    log.info("msg=gocryptfs_initialized")
    await hooks.emit(Events.GOCRYPTFS_INITIALIZED)
