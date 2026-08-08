# app/schemas/user_root.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field


class UserRootRequest(BaseModel):
    """
    Request schema for one-time root user bootstrap.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    master_password: str = Field(
        description=(
            "Master password proving ownership of the encrypted storage."
        ),
    )


class UserRootResponse(BaseModel):
    """
    One-time root credentials. secret_access_key is returned only here.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    user_id: int = Field(
        description="Root user id.",
    )
    username: str = Field(
        description="Root username.",
    )
    access_key_id: str = Field(
        description="Public access key id for SigV4.",
    )
    secret_access_key: str = Field(
        description=(
            "Secret access key plaintext. Shown only in this response."
        ),
    )
