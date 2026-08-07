# app/services/gocryptfs_password_change.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.constants import GOCRYPTFS_CIPHERDIR_LOCK_PATH, OBSCURED_VALUE
from app.errors import (
    ResourceNotFoundError,
    TooManyRequestsError,
    ValueInvalidError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.repositories.file import isfile, read, write
from app.runtime.cipherdir import is_cipherdir_created
from app.security.encryption import decrypt_passphrase, encrypt_passphrase

log = logging.getLogger(__name__)


async def gocryptfs_password_change(
    current_master_password: str,
    changed_master_password: str,
) -> None:
    """
    Change the master password protecting the stored gocryptfs
    passphrase by decrypting it with the current password,
    re-encrypting it with the new password, and persisting it.
    """
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE,
    ):
        if not await is_cipherdir_created(config.INSTALL_CIPHERDIR):
            log.warning("msg=cipherdir_not_created")
            raise ResourceNotFoundError

        if not await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
            log.warning("msg=passphrase_not_found")
            raise ResourceNotFoundError

        passphrase_encrypted = await read(
            config.GOCRYPTFS_PASSPHRASE_ENCRYPTED_PATH,
        )

        try:
            passphrase = decrypt_passphrase(
                passphrase_encrypted,
                current_master_password.encode("utf-8"),
            )
        except ValueError:
            log.warning("event=%s", E.CIPHERDIR_PASSWORD_CHANGE_PASSPHRASE_INVALID)  # noqa: E501
            raise ValueInvalidError(
                field="current_master_password",
                input_value=OBSCURED_VALUE,
            )

        passphrase_encrypted_changed = encrypt_passphrase(
            passphrase,
            changed_master_password.encode("utf-8"),
        )

        await write(
            config.GOCRYPTFS_PASSPHRASE_ENCRYPTED_PATH,
            passphrase_encrypted_changed,
        )

        log.info("event=%s", E.CIPHERDIR_PASSWORD_CHANGE_COMPLETED)
        await hooks.emit(E.CIPHERDIR_PASSWORD_CHANGE_COMPLETED)
