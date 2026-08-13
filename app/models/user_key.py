# app/models/user_key.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserKey(Base):
    """
    S3 access key pair for a user. access_key_id is public;
    secret_access_key_encrypted is recoverable ciphertext used to
    verify SigV4 signatures.
    """

    __tablename__ = "users_keys"

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

    access_key_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
    )

    secret_access_key_encrypted: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("1"),
        index=True,
    )

    user_key_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_keys",
        lazy="raise",
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
