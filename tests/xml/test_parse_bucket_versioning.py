# tests/xml/test_parse_bucket_versioning.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import (
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
    S3_XMLNS,
)
from app.xml.parse_bucket_versioning import parse_bucket_versioning


class TestParseBucketVersioning(unittest.TestCase):
    def test_parses_enabled_status(self):
        body = (
            b"<VersioningConfiguration>"
            b"<Status>Enabled</Status>"
            b"</VersioningConfiguration>"
        )

        self.assertEqual(
            parse_bucket_versioning(body),
            BUCKET_VERSIONING_ENABLED,
        )

    def test_parses_suspended_status(self):
        body = (
            b"<VersioningConfiguration>"
            b"<Status>Suspended</Status>"
            b"</VersioningConfiguration>"
        )

        self.assertEqual(
            parse_bucket_versioning(body),
            BUCKET_VERSIONING_SUSPENDED,
        )

    def test_parses_namespaced_status(self):
        body = (
            f'<VersioningConfiguration xmlns="{S3_XMLNS}">'
            "<Status>Enabled</Status>"
            "</VersioningConfiguration>"
        ).encode()

        self.assertEqual(
            parse_bucket_versioning(body),
            BUCKET_VERSIONING_ENABLED,
        )

    def test_strips_status_whitespace(self):
        body = (
            b"<VersioningConfiguration>\n"
            b"  <Status>  Enabled  </Status>\n"
            b"</VersioningConfiguration>\n"
        )

        self.assertEqual(
            parse_bucket_versioning(body),
            BUCKET_VERSIONING_ENABLED,
        )

    def test_ignores_unknown_children(self):
        body = (
            b"<VersioningConfiguration>"
            b"<MfaDelete>Enabled</MfaDelete>"
            b"<Status>Enabled</Status>"
            b"</VersioningConfiguration>"
        )

        self.assertEqual(
            parse_bucket_versioning(body),
            BUCKET_VERSIONING_ENABLED,
        )

    def test_uses_first_status(self):
        body = (
            b"<VersioningConfiguration>"
            b"<Status>Enabled</Status>"
            b"<Status>Suspended</Status>"
            b"</VersioningConfiguration>"
        )

        self.assertEqual(
            parse_bucket_versioning(body),
            BUCKET_VERSIONING_ENABLED,
        )

    def test_rejects_malformed_xml(self):
        with self.assertRaises(ValueError) as cm:
            parse_bucket_versioning(b"<VersioningConfiguration>")

        self.assertEqual(
            str(cm.exception),
            "Malformed VersioningConfiguration.",
        )

    def test_rejects_unexpected_root(self):
        with self.assertRaises(ValueError):
            parse_bucket_versioning(
                b"<Nope><Status>Enabled</Status></Nope>",
            )

    def test_rejects_missing_status(self):
        with self.assertRaises(ValueError):
            parse_bucket_versioning(
                b"<VersioningConfiguration></VersioningConfiguration>",
            )

    def test_rejects_empty_status(self):
        with self.assertRaises(ValueError):
            parse_bucket_versioning(
                b"<VersioningConfiguration>"
                b"<Status></Status>"
                b"</VersioningConfiguration>",
            )

    def test_rejects_whitespace_only_status(self):
        with self.assertRaises(ValueError):
            parse_bucket_versioning(
                b"<VersioningConfiguration>"
                b"<Status>   </Status>"
                b"</VersioningConfiguration>",
            )
