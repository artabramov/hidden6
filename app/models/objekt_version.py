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
# Current object bytes remain under the bucket directory at the S3 key,
# keeping a gocryptfs mount human-recoverable without the application.
# Non-current versions are indexed in objekts_versions and stored
# separately. The objekts row represents the current state of a key,
# while objekts_versions stores its retained version history.


class ObjektVersion(Base):
    """
    Non-current S3 object version or delete marker.

    Stores version-specific metadata for a previous state of an object
    key. Object version bytes are stored separately from current object
    bytes. Delete markers contain metadata only and have no corresponding
    object bytes.
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

    # S3 version identifier returned to clients as VersionId.
    version_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
    )

    # Size of the object version payload in bytes.
    # NULL for delete markers, which have no object payload.
    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Entity tag of the object version.
    # NULL for delete markers.
    etag: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Media type stored with the object version.
    # NULL for delete markers.
    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Whether this version record represents an S3 delete marker
    # rather than an object version with a payload.
    delete_marker: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("0"),
    )

    # S3 Object Lock retention mode: GOVERNANCE or COMPLIANCE.
    # NULL when no retention period is configured for this version.
    lock_mode: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    # Unix timestamp until which Object Lock retention protects
    # this version. NULL when no retention period is configured.
    retain_until: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Whether an S3 Object Lock legal hold is active for this version.
    # Unlike retention, a legal hold has no expiration time.
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
