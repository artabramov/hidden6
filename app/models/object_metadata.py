# app/models/object_metadata.py
# SPDX-License-Identifier: GPL-3.0-only

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ObjektMetadata(Base):
    """
    Additional metadata associated with the current S3 object state.

    Stores extensible HTTP and S3 object metadata that does not belong
    in the fixed Objekt schema, including user-defined x-amz-meta-*
    values.
    """

    __tablename__ = "objekts_metadata"

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

    meta_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    meta_value: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    objekt_metadata_objekt: Mapped["Objekt"] = relationship(  # noqa: F821
        back_populates="objekt_metadata",
        foreign_keys=[objekt_id],
        lazy="raise",
    )

    __table_args__ = (
        UniqueConstraint(
            "objekt_id",
            "meta_key",
            name="uq_objekts_metadata_objekt_meta_key",
        ),
        {"sqlite_autoincrement": True},
    )
