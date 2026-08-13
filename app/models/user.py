# app/models/user.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    Boolean,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """
    S3 user account with unique username, enabled state, and root flag.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
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

    username: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("1"),
        index=True,
    )

    is_root: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("0"),
        index=True,
    )

    users_keys: Mapped[list["UserKey"]] = relationship(  # noqa: F821
        back_populates="users_keys_users",
        passive_deletes=True,
        lazy="raise",
    )

    buckets: Mapped[list["Bucket"]] = relationship(  # noqa: F821
        back_populates="bucket_users",
        passive_deletes=True,
        lazy="raise",
    )

    objekts: Mapped[list["Objekt"]] = relationship(  # noqa: F821
        back_populates="objekts_users",
        passive_deletes=True,
        lazy="raise",
    )

    objekts_multiparts: Mapped[
        list["ObjektMultipart"]  # noqa: F821
    ] = relationship(
        back_populates="objekts_multiparts_users",
        passive_deletes=True,
        lazy="raise",
    )

    objekts_versions: Mapped[
        list["ObjektVersion"]  # noqa: F821
    ] = relationship(
        back_populates="objekts_versions_users",
        passive_deletes=True,
        lazy="raise",
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
