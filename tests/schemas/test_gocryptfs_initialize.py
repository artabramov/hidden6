# tests/schemas/test_gocryptfs_initialize.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.constants import GOCRYPTFS_MASTER_PASSWORD_MIN_LENGTH
from app.schemas.gocryptfs_initialize import GocryptfsInitializeRequest


class TestGocryptfsInitializeRequest(unittest.TestCase):

    def test_accepts_valid_master_password(self):
        req = GocryptfsInitializeRequest(
            master_password="StrongMasterPass9",
        )

        self.assertEqual(req.master_password, "StrongMasterPass9")

    def test_preserves_leading_and_trailing_whitespace(self):
        req = GocryptfsInitializeRequest(
            master_password="  StrongMasterPass9  ",
        )

        self.assertEqual(
            req.master_password,
            "  StrongMasterPass9  ",
        )

    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            GocryptfsInitializeRequest(
                master_password="StrongMasterPass9",
                other=1,
            )

    def test_master_password_required(self):
        with self.assertRaises(ValidationError):
            GocryptfsInitializeRequest()

    def test_master_password_min_length(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsInitializeRequest(
                master_password=("Aa1" * 5),
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "string_too_short")
        self.assertEqual(
            error["ctx"]["min_length"],
            GOCRYPTFS_MASTER_PASSWORD_MIN_LENGTH,
        )

    def test_rejects_password_without_lowercase(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsInitializeRequest(
                master_password="AAAAAAAAAAAAAAA1",
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "value_missing_lowercase")

    def test_rejects_password_without_uppercase(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsInitializeRequest(
                master_password="aaaaaaaaaaaaaaa1",
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "value_missing_uppercase")

    def test_rejects_password_without_digit(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsInitializeRequest(
                master_password="StrongMasterPass",
            )

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "value_missing_digit")
