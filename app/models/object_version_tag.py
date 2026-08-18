# app/models/object_version_tag.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class S3ObjectVersionTag(Base):
    """
    S3 tag associated with a non-current object version.

    Tags are stored separately from object metadata and belong to a
    specific S3 object version. Each tag key is unique within the
    version tag set.
    """

    __tablename__ = "objects_versions_tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    object_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objects_versions.id", ondelete="CASCADE"),
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

    object_version_tag_object_version: Mapped["S3ObjectVersion"] = relationship(  # noqa: E501, F821
        back_populates="object_version_tags",
        foreign_keys=[object_version_id],
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "object_version_id",
            "tag_key",
            name="uq_objects_versions_tags_version_tag_key",
        ),
        {"sqlite_autoincrement": True},
    )
