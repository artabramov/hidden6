# app/schemas/gocryptfs_health.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field


class GocryptfsHealthResponse(BaseModel):
    """
    Response schema for the gocryptfs runtime health snapshot.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    is_cipherdir_created: bool = Field(
        description="Whether the gocryptfs cipherdir appears initialized.",
    )
    is_cipherdir_mounted: bool = Field(
        description="Whether the gocryptfs mountpoint is currently mounted.",
    )
    is_watchdog_alive: bool = Field(
        description=(
            "Whether the watchdog heartbeat is fresh within "
            "WATCHDOG_LIVENESS_SECONDS."
        ),
    )
    unix_timestamp: int = Field(
        description="Current Unix timestamp in the host local timezone.",
    )
    timezone_name: str = Field(
        description="Host local timezone name (IANA, tzname, or fallback).",
    )
