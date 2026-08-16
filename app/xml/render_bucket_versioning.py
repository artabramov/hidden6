# app/xml/render_bucket_versioning.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.sax.saxutils import escape

from app.constants import S3_XMLNS


def render_bucket_versioning(
    versioning_status: str | None,
) -> str:
    """
    Render an S3-compatible VersioningConfiguration XML response.
    """
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<VersioningConfiguration xmlns="{S3_XMLNS}">',
    ]

    if versioning_status is not None:
        parts.append(
            f"<Status>{escape(versioning_status)}</Status>"
        )

    parts.append("</VersioningConfiguration>")
    return "".join(parts)
