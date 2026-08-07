# tests/schemas/test_gocryptfs_rotate.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.gocryptfs_rotate import GocryptfsRotateRequest


class TestGocryptfsRotateRequest(unittest.TestCase):

    def test_accepts_valid_payload(self):
        req = GocryptfsRotateRequest(
            current_master_password="StrongMasterKey9",
            changed_master_password="BetterMasterKey7",
        )

        self.assertEqual(req.current_master_password, "StrongMasterKey9")
        self.assertEqual(req.changed_master_password, "BetterMasterKey7")

    def test_preserves_leading_and_trailing_whitespace(self):
        req = GocryptfsRotateRequest(
            current_master_password="  StrongMasterKey9  ",
            changed_master_password="  BetterMasterKey7  ",
        )

        self.assertEqual(
            req.current_master_password,
            "  StrongMasterKey9  ",
        )
        self.assertEqual(
            req.changed_master_password,
            "  BetterMasterKey7  ",
        )

    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            GocryptfsRotateRequest(
                current_master_password="OldMasterPass9",
                changed_master_password="NewMasterPass9",
                other=1,
            )

    def test_current_master_password_required(self):
        with self.assertRaises(ValidationError):
            GocryptfsRotateRequest(
                changed_master_password="NewMasterPass9",
            )

    def test_changed_master_password_required(self):
        with self.assertRaises(ValidationError):
            GocryptfsRotateRequest(
                current_master_password="OldMasterPass9",
            )

    def test_changed_master_password_min_length(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsRotateRequest(
                current_master_password="OldMasterPass9",
                changed_master_password=("Aa1" * 5),
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("changed_master_password",))
        self.assertEqual(error["type"], "string_too_short")

    def test_rejects_changed_password_without_lowercase(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsRotateRequest(
                current_master_password="OldMasterPass9",
                changed_master_password="AAAAAAAAAAAAAAA1",
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("changed_master_password",))
        self.assertEqual(error["type"], "value_error")

    def test_rejects_changed_password_without_uppercase(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsRotateRequest(
                current_master_password="OldMasterPass9",
                changed_master_password="aaaaaaaaaaaaaaa1",
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("changed_master_password",))
        self.assertEqual(error["type"], "value_error")

    def test_rejects_changed_password_without_digit(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsRotateRequest(
                current_master_password="OldMasterPass9",
                changed_master_password="StrongMasterPass",
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("changed_master_password",))
        self.assertEqual(error["type"], "value_error")

    def test_does_not_validate_current_password_strength(self):
        req = GocryptfsRotateRequest(
            current_master_password="weak",
            changed_master_password="BetterMasterKey7",
        )

        self.assertEqual(req.current_master_password, "weak")
