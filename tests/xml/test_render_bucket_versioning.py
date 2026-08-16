# tests/xml/test_render_bucket_versioning.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import (
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
    S3_XMLNS,
)
from app.xml.render_bucket_versioning import render_bucket_versioning


class TestRenderBucketVersioning(unittest.TestCase):
    def test_omits_status_when_absent(self):
        xml = render_bucket_versioning(None)

        self.assertEqual(
            xml,
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<VersioningConfiguration xmlns="{S3_XMLNS}">'
                "</VersioningConfiguration>"
            ),
        )
        self.assertNotIn("<Status>", xml)

    def test_renders_enabled_status(self):
        xml = render_bucket_versioning(BUCKET_VERSIONING_ENABLED)

        self.assertIn(f'xmlns="{S3_XMLNS}"', xml)
        self.assertIn(
            f"<Status>{BUCKET_VERSIONING_ENABLED}</Status>",
            xml,
        )

    def test_renders_suspended_status(self):
        xml = render_bucket_versioning(BUCKET_VERSIONING_SUSPENDED)

        self.assertIn(
            f"<Status>{BUCKET_VERSIONING_SUSPENDED}</Status>",
            xml,
        )

    def test_escapes_status(self):
        xml = render_bucket_versioning("a&b<c>")

        self.assertIn("<Status>a&amp;b&lt;c&gt;</Status>", xml)
