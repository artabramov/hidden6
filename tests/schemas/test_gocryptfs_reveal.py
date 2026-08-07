# tests/schemas/test_gocryptfs_reveal.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.gocryptfs_reveal import (
    GocryptfsRevealRequest,
    GocryptfsRevealResponse,
)


class TestGocryptfsRevealRequest(unittest.TestCase):

    def test_accepts_valid_master_password(self):
        req = GocryptfsRevealRequest(
            master_password="StrongMasterKey9",
        )

        self.assertEqual(req.master_password, "StrongMasterKey9")

    def test_preserves_leading_and_trailing_whitespace(self):
        req = GocryptfsRevealRequest(
            master_password="  StrongMasterKey9  ",
        )

        self.assertEqual(req.master_password, "  StrongMasterKey9  ")

    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            GocryptfsRevealRequest(
                master_password="StrongMasterKey9",
                other=1,
            )

    def test_master_password_required(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsRevealRequest()

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "missing")


class TestGocryptfsRevealResponse(unittest.TestCase):

    def test_accepts_passphrase(self):
        resp = GocryptfsRevealResponse(
            gocryptfs_passphrase="plain-passphrase",
        )

        self.assertEqual(resp.gocryptfs_passphrase, "plain-passphrase")

    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            GocryptfsRevealResponse(
                gocryptfs_passphrase="plain-passphrase",
                other=1,
            )

    def test_passphrase_required(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsRevealResponse()

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("gocryptfs_passphrase",))
        self.assertEqual(error["type"], "missing")
