# app/models/objekt_tag.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjektTag(Base):
    """
    S3 tag associated with the current state of an object key.

    Tags are stored separately from object metadata and are managed
    through the S3 object tagging API. Each tag key is unique within
    the object tag set.
    """

    __tablename__ = "objekts_tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    objekt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objekts.id", ondelete="CASCADE"),
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

    objekt_tag_objekt: Mapped["Objekt"] = relationship(  # noqa: F821
        back_populates="objekt_tags",
        foreign_keys=[objekt_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "objekt_id",
            "tag_key",
            name="uq_objekts_tags_objekt_tag_key",
        ),
        {"sqlite_autoincrement": True},
    )
