# app/models/object_version.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# NOTE (ADR-26): S3 versioning keeps the current object on the key path.
# Current object bytes remain under the bucket directory at the S3 key,
# keeping a gocryptfs mount human-recoverable without the application.
# Non-current versions are indexed in objects_versions and stored
# separately. The objects row represents the current state of a key,
# while objects_versions stores its retained version history.


class ObjectVersion(Base):
    """
    Non-current S3 object version or delete marker.

    Stores version-specific metadata for a previous state of an object
    key. Object version bytes are stored separately from current object
    bytes. Delete markers contain metadata only and have no corresponding
    object bytes.
    """

    __tablename__ = "objects_versions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    object_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objects.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Unix timestamp when this version was moved to version history.
    # This is internal data and is not exposed through the S3 API.
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    # Unix timestamp corresponding to the S3 Last-Modified
    # value of this object version.
    modified_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
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

    object_version_object: Mapped["Objekt"] = relationship(  # noqa: F821
        back_populates="object_versions",
        foreign_keys=[object_id],
        lazy="raise",
    )

    object_version_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_objects_versions",
        foreign_keys=[user_id],
        lazy="raise",
    )

    object_version_metadata: Mapped[list["ObjectVersionMetadata"]] = relationship(  # noqa: E501, F821
        back_populates="object_version_metadata_object_version",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    object_version_tags: Mapped[list["ObjectVersionTag"]] = relationship(  # noqa: E501, F821
        back_populates="object_version_tag_object_version",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(
            """
            (
                delete_marker = 0
                AND size_bytes IS NOT NULL
                AND etag IS NOT NULL
                AND content_type IS NOT NULL
            )
            OR
            (
                delete_marker = 1
                AND size_bytes IS NULL
                AND etag IS NULL
                AND content_type IS NULL
            )
            """,
            name="ck_objects_versions_delete_marker_payload",
        ),
        CheckConstraint(
            """
            (
                lock_mode IS NULL
                AND retain_until IS NULL
            )
            OR
            (
                lock_mode IN ('GOVERNANCE', 'COMPLIANCE')
                AND retain_until IS NOT NULL
            )
            """,
            name="ck_objects_versions_object_lock_retention",
        ),
        CheckConstraint(
            """
            delete_marker = 0
            OR (
                lock_mode IS NULL
                AND retain_until IS NULL
                AND legal_hold = 0
            )
            """,
            name="ck_objects_versions_delete_marker_object_lock",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_objects_versions_size_bytes_nonnegative",
        ),
        {"sqlite_autoincrement": True},
    )
