# app/models/object_version_metadata.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjektVersionMetadata(Base):
    """
    Additional metadata associated with a non-current S3 object version.

    Stores extensible HTTP and S3 object metadata that does not belong
    in the fixed ObjektVersion schema, including user-defined x-amz-meta-*
    values.
    """

    __tablename__ = "objekts_versions_metadata"

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

    meta_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    meta_value: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    objekt_version_metadata_objekt_version: Mapped["ObjektVersion"] = relationship(  # noqa: E501, F821
        back_populates="objekt_version_metadata",
        foreign_keys=[objekt_version_id],
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "objekt_version_id",
            "meta_key",
            name="uq_objekts_versions_metadata_version_meta_key",
        ),
        {"sqlite_autoincrement": True},
    )
