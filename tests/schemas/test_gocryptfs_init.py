# tests/schemas/test_gocryptfs_init.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.gocryptfs_init import GocryptfsInitRequest


class TestGocryptfsInitRequest(unittest.TestCase):

    def test_accepts_valid_master_password(self):
        req = GocryptfsInitRequest(
            master_password="StrongMasterPass9",
        )

        self.assertEqual(req.master_password, "StrongMasterPass9")

    def test_preserves_leading_and_trailing_whitespace(self):
        req = GocryptfsInitRequest(
            master_password="  StrongMasterPass9  ",
        )

        self.assertEqual(
            req.master_password,
            "  StrongMasterPass9  ",
        )

    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            GocryptfsInitRequest(
                master_password="StrongMasterPass9",
                other=1,
            )

    def test_master_password_required(self):
        with self.assertRaises(ValidationError):
            GocryptfsInitRequest()

    def test_master_password_min_length(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsInitRequest(
                master_password=("Aa1" * 5),
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "string_too_short")
