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

    user_keys: Mapped[list["UserKey"]] = relationship(  # noqa: F821
        back_populates="user_key_user",
        lazy="raise",
    )

    user_buckets: Mapped[list["Bucket"]] = relationship(  # noqa: F821
        back_populates="bucket_user",
        lazy="raise",
    )

    user_objects: Mapped[list["S3Object"]] = relationship(  # noqa: F821
        back_populates="object_user",
        lazy="raise",
    )

    user_objects_multiparts: Mapped[list["ObjectMultipart"]] = relationship(  # noqa: E501, F821
        back_populates="object_multipart_user",
        lazy="raise",
    )

    user_objects_versions: Mapped[list["ObjectVersion"]] = relationship(  # noqa: E501, F821
        back_populates="object_version_user",
        lazy="raise",
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
