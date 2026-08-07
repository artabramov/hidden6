# app/models/user_policy.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserPolicy(Base):
    """
    Identity policy attached to a user. policy_document stores an
    IAM-style JSON policy (Version / Statement / Action / Resource /
    Effect).
    """

    __tablename__ = "users_policies"

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

    policy_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    policy_document: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("1"),
        index=True,
    )

    user_policy_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_policies",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "policy_name",
            name="uq_users_policies_user_id_policy_name",
        ),
        {"sqlite_autoincrement": True},
    )
