# app/models/object.py
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


class Objekt(Base):
    """
    Current S3 state for an object key inside a bucket.

    The row represents exactly one current state of a key. That state
    may be either an object with stored bytes or an S3 delete marker.

    With versioning disabled, writes replace the current state without
    retaining previous versions.

    With versioning enabled, every new PUT creates a new version
    identifier. Before the current state is replaced, its metadata is
    copied to ObjectVersion and its bytes are moved to version storage.
    The new state then becomes current.

    A normal DELETE in a versioning-enabled bucket does not remove
    previous object versions. Instead, it creates a new delete marker
    as the current state. Previous object versions remain available by
    version ID.

    Writing the same key after a delete marker creates a new current
    object version. The delete marker remains in version history.

    Deleting a specific version removes that version permanently.
    If the deleted version is the current state, the newest remaining
    historical state becomes current. That state may itself be either
    an object version or a delete marker.

    With versioning suspended, existing named versions are retained
    while new writes follow S3 null-version semantics.

    Object Lock applies to individual object versions, not to the key
    as a whole. Retention mode and retain-until time protect a version
    for a defined period, while legal hold protects it independently
    and without an expiration time. Delete markers do not carry Object
    Lock protection.

    Object payload metadata is present only when the current state
    represents stored object data. Delete markers have no size, ETag,
    content type, or corresponding object bytes.
    """

    __tablename__ = "objects"

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

    object_bucket: Mapped["Bucket"] = relationship(  # noqa: F821
        back_populates="bucket_objects",
        lazy="raise",
    )

    object_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_objects",
        lazy="raise",
    )

    object_versions: Mapped[list["ObjectVersion"]] = relationship(  # noqa: E501, F821
        back_populates="object_version_object",
        foreign_keys="ObjectVersion.object_id",
        lazy="raise",
    )

    object_metadata: Mapped[list["ObjectMetadata"]] = relationship(  # noqa: E501, F821
        back_populates="object_metadata_object",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    object_tags: Mapped[list["ObjectTag"]] = relationship(  # noqa: F821
        back_populates="object_tag_object",
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
            name="ck_objects_delete_marker_payload",
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
            name="ck_objects_object_lock_retention",
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
            name="ck_objects_delete_marker_object_lock",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_objects_size_bytes_nonnegative",
        ),
        UniqueConstraint(
            "bucket_id",
            "object_key",
            name="uq_objects_bucket_id_object_key",
        ),
        {"sqlite_autoincrement": True},
    )
