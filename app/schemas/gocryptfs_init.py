# app/schemas/gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field


class GocryptfsInitRequest(BaseModel):
    """
    Request schema for creating the encrypted storage requiring
    a master password.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    master_password: str = Field(
        min_length=16,
        max_length=1024,
        description="Master password used to initialize the cipherdir.",
    )
