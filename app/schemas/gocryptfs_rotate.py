# app/schemas/gocryptfs_rotate.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validators.master_password import validate_master_password


class GocryptfsRotateRequest(BaseModel):
    """
    Request schema for changing the encrypted storage master password
    with validation of the new password strength and length.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    current_master_password: str = Field(
        description="Current master password used for authentication.",
    )

    changed_master_password: str = Field(
        min_length=16,
        max_length=1024,
        description="New master password to replace the current one.",
    )

    @field_validator("changed_master_password")
    @classmethod
    def validate_changed_master_password(cls, value: str) -> str:
        return validate_master_password(value)
