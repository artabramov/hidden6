# app/services/gocryptfs_rotate.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.errors import UnauthorizedError
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.file import read, write
from app.security.encryption import decrypt_passphrase, encrypt_passphrase

log = logging.getLogger(__name__)


async def gocryptfs_rotate(
    current_master_password: str,
    changed_master_password: str,
) -> None:
    """
    Rotate the master password protecting the stored gocryptfs
    passphrase by decrypting it with the current password,
    re-encrypting it with the new password, and persisting it.
    """
    log.info("msg=gocryptfs_rotate_started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE,
    ):
        passphrase_encrypted = await read(config.GOCRYPTFS_PASSPHRASE_PATH)

        try:
            passphrase = decrypt_passphrase(
                passphrase_encrypted,
                current_master_password.encode("utf-8"),
            )

        except ValueError:
            log.warning("msg=passphrase_invalid")
            raise UnauthorizedError

        passphrase_encrypted_changed = encrypt_passphrase(
            passphrase,
            changed_master_password.encode("utf-8"),
        )

        await write(
            config.GOCRYPTFS_PASSPHRASE_PATH,
            passphrase_encrypted_changed,
        )

    log.info("msg=gocryptfs_rotated")
    await hooks.emit(Events.GOCRYPTFS_ROTATED)
