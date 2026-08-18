# app/models/object_multipart_tag.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class S3S3ObjectMultipartTag(Base):
    """
    S3 tag associated with an in-progress multipart upload.

    Tags are supplied when the multipart upload is created and are
    applied to the final object when the upload is completed. Each tag
    key is unique within the multipart upload tag set.
    """

    __tablename__ = "objects_multiparts_tags"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    object_multipart_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objects_multiparts.id", ondelete="CASCADE"),
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

    object_multipart_tag_object_multipart: Mapped["S3ObjectMultipart"] = relationship(  # noqa: E501, F821
        back_populates="object_multipart_tags",
        foreign_keys=[object_multipart_id],
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "object_multipart_id",
            "tag_key",
            name="uq_objects_multiparts_tags_multipart_tag_key",
        ),
        {"sqlite_autoincrement": True},
    )
