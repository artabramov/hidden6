# app/models/objekt_multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
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
    In-progress S3 multipart upload. The row lives from
    CreateMultipartUpload until the upload is completed or aborted;
    completion turns the staged parts into a single Objekt.
    """

    __tablename__ = "objekts_multiparts"

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

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        default=lambda: int(time.time()),
    )

    updated_at: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        onupdate=lambda: int(time.time()),
    )

    upload_id: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
    )

    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    objekt_multipart_bucket: Mapped["Bucket"] = relationship(  # noqa: F821
        back_populates="bucket_objekts_multiparts",
    )

    objekt_multipart_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_objekts_multiparts",
    )

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )
