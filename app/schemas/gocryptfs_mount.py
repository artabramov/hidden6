# app/schemas/gocryptfs_mount.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field


class GocryptfsMountRequest(BaseModel):
    """
    Request schema for mounting the storage mountpoint requiring
    the master password for decryption.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    master_password: str = Field(
        description="Master password used to mount the cipherdir.",
    )
