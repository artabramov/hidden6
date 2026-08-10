# app/models/bucket.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# NOTE (ADR-21): S3 authorization is owner-and-root (no IAM policies).
# Authorization is based on bucket ownership. Non-root users may access
# only their own buckets; root may access any bucket. IAM and bucket
# policies are not evaluated.


class Bucket(Base):
    """
    S3 bucket owned by a user. bucket_name is unique across the store
    and matches the on-disk directory under the mountpoint buckets dir.
    """

    __tablename__ = "buckets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    updated_at: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        onupdate=lambda: int(time.time()),
    )

    bucket_name: Mapped[str] = mapped_column(
        String(63),
        nullable=False,
        unique=True,
    )

    bucket_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="buckets",
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
