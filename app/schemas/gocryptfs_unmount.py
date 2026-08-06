# app/schemas/gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field


class GocryptfsUnmountRequest(BaseModel):
    """
    Request schema for unmounting the storage mountpoint requiring
    the master password for authorization.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    master_password: str = Field(
        description="Master password used to unmount the cipherdir.",
    )
