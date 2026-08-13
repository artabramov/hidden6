# app/models/objekt.py
# SPDX-License-Identifier: GPL-3.0-only

import time

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# NOTE (ADR-23): S3 object names do not collide with Python builtins.
# The ORM model for S3 objects is named Objekt (table objekts) so local
# names never shadow the builtin object. Wire protocol names such as
# PutObject and object key remain S3-native.


class Objekt(Base):
    """
    S3 object metadata for a key inside a bucket. Object bytes live on
    disk under the bucket directory; this row indexes size, ETag,
    content type, and the uploading user for ListObjects / HeadObject /
    GetObject / PutObject.
    """

    __tablename__ = "objekts"

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

    updated_at: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        onupdate=lambda: int(time.time()),
    )

    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    etag: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    objekt_bucket: Mapped["Bucket"] = relationship(  # noqa: F821
        back_populates="bucket_objekts",
        lazy="raise",
    )

    objekt_user: Mapped["User"] = relationship(  # noqa: F821
        back_populates="user_objekts",
        lazy="raise",
    )

    objekt_versions: Mapped[list["ObjektVersion"]] = relationship(  # noqa: E501, F821
        back_populates="objekt_version_objekt",
        foreign_keys="ObjektVersion.objekt_id",
        passive_deletes=True,
        lazy="raise",
    )

    objekt_metadata: Mapped[list["ObjektMetadata"]] = relationship(
        back_populates="objekt_metadata_objekt",
        cascade="all, delete-orphan",
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "bucket_id",
            "object_key",
            name="uq_objekts_bucket_id_object_key",
        ),
        {"sqlite_autoincrement": True},
    )
