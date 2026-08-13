# app/models/objekt_multipart_metadata.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjektMultipartMetadata(Base):
    """
    Additional metadata associated with an in-progress multipart upload.

    Stores extensible HTTP and S3 object metadata supplied when the
    multipart upload is created. The metadata is applied to the final
    object when the upload is completed.
    """

    __tablename__ = "objekts_multiparts_metadata"

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

    metadata_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    metadata_value: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    objekt_multipart_metadata_objekt_multipart: Mapped["ObjektMultipart"] = relationship(  # noqa: E501, F821
        back_populates="objekt_multipart_metadata",
        foreign_keys=[objekt_multipart_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "objekt_multipart_id",
            "metadata_key",
            name="uq_objekts_multiparts_metadata_multipart_metadata_key",
        ),
        {"sqlite_autoincrement": True},
    )
