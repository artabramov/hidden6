# app/models/objekt_multipart_tag.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjektMultipartTag(Base):
    """
    S3 tag associated with an in-progress multipart upload.

    Tags are supplied when the multipart upload is created and are
    applied to the final object when the upload is completed. Each tag
    key is unique within the multipart upload tag set.
    """

    __tablename__ = "objekts_multiparts_tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    objekt_multipart_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objekts_multiparts.id", ondelete="CASCADE"),
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

    objekt_multipart_tag_objekt_multipart: Mapped["ObjektMultipart"] = relationship(  # noqa: E501, F821
        back_populates="objekt_multipart_tags",
        foreign_keys=[objekt_multipart_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "objekt_multipart_id",
            "tag_key",
            name="uq_objekts_multiparts_tags_multipart_tag_key",
        ),
        {"sqlite_autoincrement": True},
    )
