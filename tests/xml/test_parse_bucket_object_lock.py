# tests/xml/test_parse_bucket_object_lock.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.constants import S3_XMLNS
from app.xml.parse_bucket_object_lock import parse_bucket_object_lock


class TestParseBucketObjektLock(unittest.TestCase):
    def test_parses_enabled_without_rule(self):
        body = (
            b"<ObjectLockConfiguration>"
            b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
            b"</ObjectLockConfiguration>"
        )

        self.assertEqual(
            parse_bucket_object_lock(body),
            ("Enabled", None, None, None),
        )

    def test_parses_governance_days(self):
        body = (
            b"<ObjectLockConfiguration>"
            b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
            b"<Rule><DefaultRetention>"
            b"<Mode>GOVERNANCE</Mode>"
            b"<Days>10</Days>"
            b"</DefaultRetention></Rule>"
            b"</ObjectLockConfiguration>"
        )

        self.assertEqual(
            parse_bucket_object_lock(body),
            ("Enabled", "GOVERNANCE", 10, None),
        )

    def test_parses_compliance_years(self):
        body = (
            b"<ObjectLockConfiguration>"
            b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
            b"<Rule><DefaultRetention>"
            b"<Mode>COMPLIANCE</Mode>"
            b"<Years>2</Years>"
            b"</DefaultRetention></Rule>"
            b"</ObjectLockConfiguration>"
        )

        self.assertEqual(
            parse_bucket_object_lock(body),
            ("Enabled", "COMPLIANCE", None, 2),
        )

    def test_parses_namespaced_configuration(self):
        body = (
            f'<ObjectLockConfiguration xmlns="{S3_XMLNS}">'
            "<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
            "<Rule><DefaultRetention>"
            "<Mode>GOVERNANCE</Mode>"
            "<Days>1</Days>"
            "</DefaultRetention></Rule>"
            "</ObjectLockConfiguration>"
        ).encode()

        self.assertEqual(
            parse_bucket_object_lock(body),
            ("Enabled", "GOVERNANCE", 1, None),
        )

    def test_strips_field_whitespace(self):
        body = (
            b"<ObjectLockConfiguration>\n"
            b"  <ObjectLockEnabled>  Enabled  </ObjectLockEnabled>\n"
            b"  <Rule>\n"
            b"    <DefaultRetention>\n"
            b"      <Mode>  GOVERNANCE  </Mode>\n"
            b"      <Days>  7  </Days>\n"
            b"    </DefaultRetention>\n"
            b"  </Rule>\n"
            b"</ObjectLockConfiguration>\n"
        )

        self.assertEqual(
            parse_bucket_object_lock(body),
            ("Enabled", "GOVERNANCE", 7, None),
        )

    def test_empty_configuration_returns_nones(self):
        body = b"<ObjectLockConfiguration></ObjectLockConfiguration>"

        self.assertEqual(
            parse_bucket_object_lock(body),
            (None, None, None, None),
        )

    def test_rejects_unknown_children(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<Extra>nope</Extra>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_unknown_retention_children(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Checksum>deadbeef</Checksum>"
                b"<Mode>COMPLIANCE</Mode>"
                b"<Years>1</Years>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_malformed_xml(self):
        with self.assertRaises(ValueError) as cm:
            parse_bucket_object_lock(b"<ObjectLockConfiguration>")

        self.assertEqual(
            str(cm.exception),
            "Malformed ObjectLockConfiguration.",
        )

    def test_rejects_unexpected_root(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<Nope><ObjectLockEnabled>Enabled</ObjectLockEnabled></Nope>",
            )

    def test_rejects_empty_object_lock_enabled(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled></ObjectLockEnabled>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_non_enabled_object_lock(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Disabled</ObjectLockEnabled>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_rule_without_default_retention(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_rule_with_extra_children(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule>"
                b"<DefaultRetention>"
                b"<Mode>GOVERNANCE</Mode>"
                b"<Days>1</Days>"
                b"</DefaultRetention>"
                b"<Extra/>"
                b"</Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_missing_mode(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Days>10</Days>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_invalid_mode(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Mode>INVALID</Mode>"
                b"<Days>10</Days>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_both_days_and_years(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Mode>GOVERNANCE</Mode>"
                b"<Days>10</Days>"
                b"<Years>1</Years>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_neither_days_nor_years(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Mode>GOVERNANCE</Mode>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_non_positive_days(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Mode>GOVERNANCE</Mode>"
                b"<Days>0</Days>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_non_positive_years(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Mode>COMPLIANCE</Mode>"
                b"<Years>0</Years>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_non_numeric_days(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Mode>GOVERNANCE</Mode>"
                b"<Days>ten</Days>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )

    def test_rejects_non_numeric_years(self):
        with self.assertRaises(ValueError):
            parse_bucket_object_lock(
                b"<ObjectLockConfiguration>"
                b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                b"<Rule><DefaultRetention>"
                b"<Mode>COMPLIANCE</Mode>"
                b"<Years>two</Years>"
                b"</DefaultRetention></Rule>"
                b"</ObjectLockConfiguration>",
            )
