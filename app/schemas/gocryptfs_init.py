# app/schemas/gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validators.master_password import validate_master_password


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

    @field_validator("master_password")
    @classmethod
    def validate_master_password_field(cls, value: str) -> str:
        return validate_master_password(value)
