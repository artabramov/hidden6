# app/dependencies/require_gocryptfs.py
# SPDX-License-Identifier: GPL-3.0-only

import logging

from app.config import get_config
from app.errors import ServiceUnavailableError, BadGatewayError
from app.runtime.cipherdir import is_cipherdir_created
from app.repositories.file import isfile, ismount

log = logging.getLogger(__name__)

# NOTE (ADR-08): Gocryptfs dependency executes before all others.
# FastAPI prepends decorator dependencies= to the endpoint dependency
# list and solves them sequentially with await. Registering the check
# there guarantees it runs before signature Depends (e.g. get_session)
# and aborts the request before any database session is opened.


def require_gocryptfs(
    require_cipherdir: bool = True,
    require_mountpoint: bool = True,
    require_passphrase: bool = True,
):
    """
    FastAPI dependency factory to check gocryptfs preconditions.

    Returns a dynamic dependency wrapper tailored for either standard
    operational checks (ensuring resources exist) or initialization
    routines (ensuring resources do not conflict).
    """

    async def check_gocryptfs() -> None:
        """
        Execute fail-fast validation for gocryptfs paths and states.

        Evaluates the status of the cipher directory, the mountpoint,
        and the passphrase file based on the factory configuration.

        Raises:
            ServiceUnavailableError: Required resource is missing (503).
            BadGatewayError: Resource exists when it should not (502).
        """
        config = get_config()

        # Scenario 1: validate cipherdir existence or absence

        if (
            require_cipherdir
            and not await is_cipherdir_created(config.INSTALL_CIPHERDIR)
        ):
            log.warning("msg=cipherdir_not_found")
            raise ServiceUnavailableError

        elif (
            not require_cipherdir
            and await is_cipherdir_created(config.INSTALL_CIPHERDIR)
        ):
            log.warning("msg=cipherdir_exists")
            raise BadGatewayError

        # Scenario 2: validate mountpoint existence or absence

        if (
            require_mountpoint
            and not await ismount(config.INSTALL_MOUNTPOINT)
        ):
            log.warning("msg=mountpoint_not_found")
            raise ServiceUnavailableError

        elif (
            not require_mountpoint
            and await ismount(config.INSTALL_MOUNTPOINT)
        ):
            log.warning("msg=mountpoint_exists")
            raise BadGatewayError

        # Scenario 3: validate passphrase existence or absence

        if (
            require_passphrase
            and not await isfile(config.GOCRYPTFS_PASSPHRASE_PATH)
        ):
            log.warning("msg=passphrase_not_found")
            raise ServiceUnavailableError

        elif (
            not require_passphrase
            and await isfile(config.GOCRYPTFS_PASSPHRASE_PATH)
        ):
            log.warning("msg=passphrase_exists")
            raise BadGatewayError

    return check_gocryptfs
