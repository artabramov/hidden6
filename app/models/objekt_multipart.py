# app/models/objekt_multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# NOTE (ADR-26): S3 multipart uploads are tracked in the database.
# A row binds the upload id issued to the client to its bucket, key,
# and initiating user, so every part and the final assembly can be
# authorized. Part bytes are staged in the mountpoint tmp dir and
# exist only until the upload is completed or aborted.


class ObjektMultipart(Base):
    """
    In-progress S3 multipart upload.

    Tracks the target object and metadata from CreateMultipartUpload
    until the upload is completed or aborted. Uploaded part bytes are
    staged separately and assembled into the final object on completion.
    """

    __tablename__ = "objekts_multiparts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    bucket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("buckets.id"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    # S3 multipart upload identifier exposed to clients as UploadId.
    upload_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
    )

    # Target S3 object key for the completed multipart upload.
    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # Media type assigned to the final object on completion.
    content_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("'application/octet-stream'"),
    )

    objekt_multipart_bucket: Mapped["Bucket"] = relationship(  # noqa: F821
        back_populates="bucket_objekts_multiparts",
        lazy="raise",
    )

    objekt_multipart_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_objekts_multiparts",
        lazy="raise",
    )

    objekt_multipart_parts: Mapped[list["ObjektMultipartPart"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_multipart_part_objekt_multipart",
        lazy="raise",
    )

    objekt_multipart_metadata: Mapped[list["ObjektMultipartMetadata"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_multipart_metadata_objekt_multipart",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    objekt_multipart_tags: Mapped[list["ObjektMultipartTag"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_multipart_tag_objekt_multipart",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
