# app/models/bucket.py
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

from app.constants import BUCKET_VERSIONING_DISABLED
from app.db.base import Base

# NOTE (ADR-21): S3 authorization is owner-and-root (no IAM policies).
# Authorization is based on bucket ownership. Non-root users may access
# only their own buckets; root may access any bucket. IAM and bucket
# policies are not evaluated.


class Bucket(Base):
    """
    S3 bucket owned by a user.

    The bucket name is unique across the store and maps directly to
    its on-disk directory.

    Versioning has three internal states: Disabled, Enabled, and
    Suspended. Disabled represents a bucket where S3 versioning has not
    been enabled and is exposed through the API without a Status value.
    Enabled creates uniquely identified object versions, while Suspended
    preserves existing versions and applies S3 null-version semantics to
    new writes.

    Object Lock is a bucket-level capability. Enabling it requires
    versioning to remain Enabled and cannot be reversed. When Object
    Lock is enabled, the bucket may define a default retention rule
    using either GOVERNANCE or COMPLIANCE mode together with a
    retention period expressed in days or years.

    Default retention applies to new object versions unless the request
    provides explicit Object Lock settings. Legal holds and per-version
    retention state are stored on the corresponding object version
    rather than on the bucket.

    Bucket deletion is allowed only after its object state and
    in-progress multipart uploads have been removed explicitly.
    """

    __tablename__ = "buckets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # Unix timestamp when the bucket was created.
    # Corresponds to the S3 CreationDate value.
    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    bucket_name: Mapped[str] = mapped_column(
        String(63),
        nullable=False,
        unique=True,
    )

    # Internal bucket versioning state.
    # Disabled maps to an S3 configuration with no Status value.
    versioning_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text(f"'{BUCKET_VERSIONING_DISABLED}'"),
        index=True,
    )

    # Whether S3 Object Lock is enabled for this bucket.
    # Once enabled, Object Lock cannot be disabled.
    object_lock_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("0"),
    )

    # Default Object Lock retention mode applied to new object versions.
    # NULL when no default retention rule is configured.
    default_lock_mode: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )

    # Default Object Lock retention period in days.
    # Mutually exclusive with default_retention_years.
    default_retention_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Default Object Lock retention period in years.
    # Mutually exclusive with default_retention_days.
    default_retention_years: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    bucket_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_buckets",
        lazy="raise",
    )

    bucket_objekts: Mapped[list["Objekt"]] = relationship(  # noqa: F821
        back_populates="objekt_bucket",
        lazy="raise",
    )

    bucket_objekts_multiparts: Mapped[list["ObjektMultipart"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_multipart_bucket",
        lazy="raise",
    )

    bucket_tags: Mapped[list["BucketTag"]] = relationship(  # noqa: F821
        back_populates="bucket_tag_bucket",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(
            "versioning_status IN ('Disabled', 'Enabled', 'Suspended')",
            name="ck_buckets_versioning_status",
        ),
        CheckConstraint(
            "default_retention_days IS NULL OR default_retention_days > 0",
            name="ck_buckets_default_retention_days_positive",
        ),
        CheckConstraint(
            "default_retention_years IS NULL OR default_retention_years > 0",
            name="ck_buckets_default_retention_years_positive",
        ),
        CheckConstraint(
            """
            (
                default_lock_mode IS NULL
                AND default_retention_days IS NULL
                AND default_retention_years IS NULL
            )
            OR
            (
                default_lock_mode IN ('GOVERNANCE', 'COMPLIANCE')
                AND (
                    (
                        default_retention_days IS NOT NULL
                        AND default_retention_years IS NULL
                    )
                    OR
                    (
                        default_retention_days IS NULL
                        AND default_retention_years IS NOT NULL
                    )
                )
            )
            """,
            name="ck_buckets_default_retention",
        ),
        CheckConstraint(
            """
            object_lock_enabled = 1
            OR (
                default_lock_mode IS NULL
                AND default_retention_days IS NULL
                AND default_retention_years IS NULL
            )
            """,
            name="ck_buckets_object_lock_default_retention",
        ),
        CheckConstraint(
            "object_lock_enabled = 0 OR versioning_status = 'Enabled'",
            name="ck_buckets_object_lock_versioning",
        ),
        {"sqlite_autoincrement": True},
    )
