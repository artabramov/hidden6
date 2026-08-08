# app/services/user_root.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_config
from app.constants import (
    USER_ROOT_USERNAME,
    USER_ACCESS_KEY_ID_LENGTH,
    USER_SECRET_ACCESS_KEY_LENGTH,
)
from app.errors import (
    ResourceConflictError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from app.hooks import Events, hooks
from app.locks import LockType, locks
from app.models.user import User
from app.models.user_key import UserKey
from app.repositories.file import isfile, ismount, read
from app.repositories.orm import ORMRepository
from app.runtime.cipherdir import is_cipherdir_created
from app.security.encryption import decrypt_passphrase, encrypt_string
from app.security.randoms import generate_random_string

log = logging.getLogger(__name__)


async def user_root(
    master_password: str,
    session: AsyncSession,
) -> dict:
    """
    Create the bootstrap root user and its first access key pair.

    Requires a mounted store and a valid master password. Fails with
    conflict if a root user already exists. Returns plaintext credentials
    once; the secret is stored only as Fernet ciphertext.
    """
    log.info("msg=user_root_started")
    config = get_config()

    async with locks.lock_directory(
        config.INSTALL_SECRETS,
        LockType.WRITE,
    ):
        if not await is_cipherdir_created(config.INSTALL_CIPHERDIR):
            log.warning("msg=cipherdir_not_created")
            raise ServiceUnavailableError

        if not await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
            log.warning("msg=passphrase_not_found")
            raise ServiceUnavailableError

        if not await ismount(config.INSTALL_MOUNTPOINT):
            log.warning("msg=cipherdir_not_mounted")
            raise ServiceUnavailableError

        passphrase_encrypted = await read(config.GOCRYPTFS_PASSPHRASE_PATH)

        try:
            decrypt_passphrase(
                passphrase_encrypted,
                master_password.encode("utf-8"),
            )

        except ValueError:
            log.warning("msg=passphrase_invalid")
            raise UnauthorizedError

    repo = ORMRepository(session)

    existing = await repo.select(User, is_root=True)
    if existing is not None:
        log.warning("msg=root_user_already_exists")
        raise ResourceConflictError

    access_key_id = generate_random_string(USER_ACCESS_KEY_ID_LENGTH)
    secret_access_key = generate_random_string(USER_SECRET_ACCESS_KEY_LENGTH)

    user = User(
        username=USER_ROOT_USERNAME,
        is_root=True,
        is_enabled=True,
    )
    await repo.insert(user)

    key = UserKey(
        user_id=user.id,
        access_key_id=access_key_id,
        secret_access_key_encrypted=encrypt_string(secret_access_key),
        is_enabled=True,
    )
    await repo.insert(key, commit=True)

    log.info("msg=user_root_completed")
    await hooks.emit(Events.USER_ROOT_CREATED, user)

    return {
        "user_id": user.id,
        "username": user.username,
        "access_key_id": access_key_id,
        "secret_access_key": secret_access_key,
    }
