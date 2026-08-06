# tests/schemas/test_gocryptfs_mount.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.gocryptfs_mount import GocryptfsMountRequest


class TestGocryptfsMountRequest(unittest.TestCase):

    def test_accepts_valid_master_password(self):
        req = GocryptfsMountRequest(
            master_password="StrongMasterKey9",
        )

        self.assertEqual(req.master_password, "StrongMasterKey9")

    def test_preserves_leading_and_trailing_whitespace(self):
        req = GocryptfsMountRequest(
            master_password="  StrongMasterKey9  ",
        )

        self.assertEqual(req.master_password, "  StrongMasterKey9  ")

    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            GocryptfsMountRequest(
                master_password="StrongMasterKey9",
                other=1,
            )

    def test_master_password_required(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsMountRequest()

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "missing")
