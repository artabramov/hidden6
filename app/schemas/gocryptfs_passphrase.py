# app/schemas/gocryptfs_passphrase.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field


class GocryptfsPassphraseRequest(BaseModel):
    """
    Request schema for revealing the stored gocryptfs passphrase
    with the master password.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    master_password: str = Field(
        description="Master password used to decrypt the passphrase.",
    )


class GocryptfsPassphraseResponse(BaseModel):
    """
    Response schema containing the decrypted gocryptfs passphrase.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    gocryptfs_passphrase: str = Field(
        description="Decrypted gocryptfs passphrase.",
    )
