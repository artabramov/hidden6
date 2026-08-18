# app/models/object_tag.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjectTag(Base):
    """
    S3 tag associated with the current state of an object key.

    Tags are stored separately from object metadata and are managed
    through the S3 object tagging API. Each tag key is unique within
    the object tag set.
    """

    __tablename__ = "objects_tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    object_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objects.id", ondelete="CASCADE"),
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

    object_tag_object: Mapped["S3Object"] = relationship(  # noqa: F821
        back_populates="object_tags",
        foreign_keys=[object_id],
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "object_id",
            "tag_key",
            name="uq_objects_tags_object_tag_key",
        ),
        {"sqlite_autoincrement": True},
    )
