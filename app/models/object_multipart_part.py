# app/models/object_multipart_part.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjektMultipartPart(Base):
    """
    Uploaded part of an in-progress S3 multipart upload.

    Stores S3 metadata for one uploaded part. Part bytes are staged
    separately on disk and are replaced when the same PartNumber is
    uploaded again for the same multipart upload.
    """

    __tablename__ = "objekts_multiparts_parts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    objekt_multipart_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("objekts_multiparts.id"),
        nullable=False,
        index=True,
    )

    # Unix timestamp corresponding to the S3 LastModified value
    # returned for this uploaded part.
    modified_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    # S3 part number supplied by the client.
    part_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Size of the uploaded part payload in bytes.
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Entity tag returned for this uploaded part and later supplied
    # by the client when completing the multipart upload.
    etag: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    objekt_multipart_part_objekt_multipart: Mapped["ObjektMultipart"] = relationship(  # noqa: E501, F821
        back_populates="objekt_multipart_parts",
        foreign_keys=[objekt_multipart_id],
        lazy="raise",
    )

    __table_args__ = (
        CheckConstraint(
            "part_number >= 1 AND part_number <= 10000",
            name="ck_objekts_multiparts_parts_part_number",
        ),
        CheckConstraint(
            "size_bytes >= 0",
            name="ck_objekts_multiparts_parts_size_bytes_nonnegative",
        ),
        UniqueConstraint(
            "objekt_multipart_id",
            "part_number",
            name="uq_objekts_multiparts_parts_multipart_part_number",
        ),
        {"sqlite_autoincrement": True},
    )
