# app/models/objekt_version_tag.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjektVersionTag(Base):
    """
    S3 tag associated with a non-current object version.

    Tags are stored separately from object metadata and belong to a
    specific S3 object version. Each tag key is unique within the
    version tag set.
    """

    __tablename__ = "objekts_versions_tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    objekt_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objekts_versions.id", ondelete="CASCADE"),
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

    objekt_version_tag_objekt_version: Mapped["ObjektVersion"] = relationship(  # noqa: E501, F821
        back_populates="objekt_version_tags",
        foreign_keys=[objekt_version_id],
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "objekt_version_id",
            "tag_key",
            name="uq_objekts_versions_tags_version_tag_key",
        ),
        {"sqlite_autoincrement": True},
    )
