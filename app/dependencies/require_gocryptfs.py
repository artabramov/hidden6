# app/dependencies/require_gocryptfs.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.errors import ServiceUnavailableError, BadGatewayError
from app.runtime.cipherdir import is_cipherdir_created
from app.repositories.file import isfile, ismount

log = logging.getLogger(__name__)

# NOTE (ADR-08): Gocryptfs dependency executes before all others.
# FastAPI resolves dependencies listed in the decorator's dependencies=
# argument before signature Depends() dependencies. Registering the
# gocryptfs check there guarantees it runs before require_session and
# aborts the request before any database session is opened.


def require_gocryptfs(
    require_cipherdir: bool | None = True,
    require_mountpoint: bool | None = True,
    require_passphrase: bool | None = True,
):
    """
    FastAPI dependency factory to check gocryptfs preconditions.

    Each resource (cipherdir, mountpoint, and passphrase) can be
    required, forbidden, or ignored by passing True, False, or
    None respectively.
    """

    async def check_gocryptfs() -> None:
        """
        Execute fail-fast validation for gocryptfs paths and states.

        Raises:
            ServiceUnavailableError: Required resource is missing (503).
            BadGatewayError: Resource exists when it should not (502).
        """
        config = get_config()

        # Scenario 1: validate cipherdir existence or absence

        if require_cipherdir is True:
            if not await is_cipherdir_created(config.INSTALL_CIPHERDIR):
                log.warning("msg=cipherdir_not_found")
                raise ServiceUnavailableError

        elif require_cipherdir is False:
            if await is_cipherdir_created(config.INSTALL_CIPHERDIR):
                log.warning("msg=cipherdir_exists")
                raise BadGatewayError

        # Scenario 2: validate mountpoint existence or absence

        if require_mountpoint is True:
            if not await ismount(config.INSTALL_MOUNTPOINT):
                log.warning("msg=mountpoint_not_found")
                raise ServiceUnavailableError

        elif require_mountpoint is False:
            if await ismount(config.INSTALL_MOUNTPOINT):
                log.warning("msg=mountpoint_exists")
                raise BadGatewayError

        # Scenario 3: validate passphrase existence or absence

        if require_passphrase is True:
            if not await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
                log.warning("msg=passphrase_not_found")
                raise ServiceUnavailableError

        elif require_passphrase is False:
            if await isfile(config.GOCRYPTFS_PASSPHRASE_PATH):
                log.warning("msg=passphrase_exists")
                raise BadGatewayError

    return check_gocryptfs
