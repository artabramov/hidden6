# app/xml/render_bucket_objekt_lock.py
# SPDX-License-Identifier: GPL-3.0-only

from app.constants import S3_XMLNS
from app.models.bucket import Bucket


def render_bucket_objekt_lock(bucket: Bucket) -> str:
    """
    Render an S3-compatible ObjectLockConfiguration XML response.
    """
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<ObjectLockConfiguration xmlns="{S3_XMLNS}">',
        "<ObjectLockEnabled>Enabled</ObjectLockEnabled>",
    ]

    if bucket.default_lock_mode is not None:
        parts.extend(
            [
                "<Rule>",
                "<DefaultRetention>",
                f"<Mode>{bucket.default_lock_mode}</Mode>",
            ]
        )

        if bucket.default_retention_days is not None:
            parts.append(
                f"<Days>{bucket.default_retention_days}</Days>"
            )
        else:
            parts.append(
                f"<Years>{bucket.default_retention_years}</Years>"
            )

        parts.extend(
            [
                "</DefaultRetention>",
                "</Rule>",
            ]
        )

    parts.append("</ObjectLockConfiguration>")
    return "".join(parts)
