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

# NOTE (ADR-27): S3 versioning keeps the current object on the key path.
# Current bytes remain under the bucket directory at the S3 object key,
# keeping a gocryptfs mount human-recoverable without the application.
# Non-current versions are indexed in objekts_versions and stored flat
# as versions/{bucket}/{version_id}. The objekts row represents the
# current state of each key. When versioning replaces or deletes an
# object, its previous metadata and bytes move into objekts_versions.
# Bucket.versioning_status selects Disabled, Enabled, or Suspended;
# version history is created only while Enabled.


class ObjektVersion(Base):
    """
    Non-current S3 object version or delete marker.

    Current object state remains in objekts. When a current object
    version becomes non-current, its metadata moves here and its bytes
    move to versions/{bucket}/{version_id}. Delete markers are stored
    as metadata-only version records and have no corresponding object
    bytes.
    """

    __tablename__ = "objekts_versions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    objekt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objekts.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
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

    version_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    etag: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    delete_marker: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("0"),
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

    objekt_version_objekt: Mapped["Objekt"] = relationship(  # noqa: F821
        back_populates="objekt_versions",
        foreign_keys=[objekt_id],
    )

    objekt_version_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_objekts_versions",
        foreign_keys=[user_id],
    )

    objekt_version_metadata: Mapped[list["ObjektVersionMetadata"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_version_metadata_objekt_version",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
