# app/models/objekt_version.py
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

# NOTE (ADR-24): Current object bytes stay on the key path under the
# bucket directory so a gocryptfs mount remains human-recoverable
# without the application. Non-current versions are stored as opaque
# uuid files under the mountpoint versions directory and indexed here.


class ObjektVersion(Base):
    """
    Non-current S3 object version (or a non-current delete marker).

    The live object for a key remains in objekts and on the key path
    under the bucket. When versioning replaces or soft-deletes that
    object, its previous metadata and bytes move here: metadata in
    this row (linked to the current objekts row via objekt_id), bytes
    at versions/{bucket}/{version_id}.
    """

    __tablename__ = "objekts_versions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    bucket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("buckets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    objekt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objekts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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

    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        index=True,
    )

    version_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
    )

    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )

    etag: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("''"),
    )

    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'application/octet-stream'"),
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("0"),
        index=True,
    )

    lock_mode: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    retain_until: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    legal_hold: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("0"),
    )

    objekts_versions_buckets: Mapped["Bucket"] = relationship(  # noqa: F821
        back_populates="objekts_versions",
        foreign_keys=[bucket_id],
    )

    objekts_versions_objekts: Mapped["Objekt"] = relationship(  # noqa: F821
        back_populates="objekts_versions",
        foreign_keys=[objekt_id],
    )

    objekts_versions_users: Mapped["User"] = relationship(  # noqa: F821
        back_populates="objekts_versions",
        foreign_keys=[user_id],
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
