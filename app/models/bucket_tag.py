# app/models/bucket_tag.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BucketTag(Base):
    """
    S3 tag associated with a bucket.

    Bucket tags are managed independently from object tags and bucket
    configuration. Each tag key is unique within the bucket tag set.
    """

    __tablename__ = "buckets_tags"

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

    tag_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    tag_value: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
    )

    bucket_tag_bucket: Mapped["Bucket"] = relationship(  # noqa: F821
        back_populates="bucket_tags",
        foreign_keys=[bucket_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "bucket_id",
            "tag_key",
            name="uq_buckets_tags_bucket_tag_key",
        ),
        {"sqlite_autoincrement": True},
    )
