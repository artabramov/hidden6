# app/models/objekt.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# NOTE (ADR-23): S3 object names do not collide with Python builtins.
# The ORM model for S3 objects is named Objekt (table objekts) so local
# names never shadow the builtin object. Wire protocol names such as
# PutObject and object key remain S3-native.


class Objekt(Base):
    """
    Current S3 state for an object key inside a bucket.

    Stores metadata for the current object version or delete marker.
    Object bytes live under the bucket directory at the S3 key when
    the current state contains object data; delete markers have no
    corresponding object bytes.
    """

    __tablename__ = "objekts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    bucket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("buckets.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Unix timestamp when the object key was first created.
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    # Unix timestamp when the current S3 state was created.
    # Corresponds to the S3 Last-Modified value.
    modified_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    # S3 object key that uniquely identifies the object
    # within its bucket.
    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # Size of the current object payload in bytes.
    # NULL when the current state is a delete marker.
    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Entity tag of the current object.
    # NULL when the current state is a delete marker.
    etag: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Media type stored with the current object.
    # NULL when the current state is a delete marker.
    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # S3 version identifier for the current state
    # of this object key.
    version_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        unique=True,
    )

    # Whether the current state represents an S3 delete marker
    # rather than an object version with stored bytes.
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

    # Whether an S3 Object Lock legal hold is active
    # for this version.
    legal_hold: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("0"),
    )

    objekt_bucket: Mapped["Bucket"] = relationship(  # noqa: F821
        back_populates="bucket_objekts",
        lazy="raise",
    )

    objekt_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_objekts",
        lazy="raise",
    )

    objekt_versions: Mapped[list["ObjektVersion"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_version_objekt",
        foreign_keys="ObjektVersion.objekt_id",
        lazy="raise",
    )

    objekt_metadata: Mapped[list["ObjektMetadata"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_metadata_objekt",
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
            name="ck_objekts_delete_marker_payload",
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
            name="ck_objekts_object_lock_retention",
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
            name="ck_objekts_delete_marker_object_lock",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_objekts_size_bytes_nonnegative",
        ),
        UniqueConstraint(
            "bucket_id",
            "object_key",
            name="uq_objekts_bucket_id_object_key",
        ),
        {"sqlite_autoincrement": True},
    )
