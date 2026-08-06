# tests/schemas/test_gocryptfs_unmount.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.gocryptfs_unmount import GocryptfsUnmountRequest


class TestGocryptfsUnmountRequest(unittest.TestCase):

    def test_accepts_valid_master_password(self):
        req = GocryptfsUnmountRequest(
            master_password="StrongMasterKey9",
        )

        self.assertEqual(req.master_password, "StrongMasterKey9")

    def test_preserves_leading_and_trailing_whitespace(self):
        req = GocryptfsUnmountRequest(
            master_password="  StrongMasterKey9  ",
        )

        self.assertEqual(req.master_password, "  StrongMasterKey9  ")

    def test_extra_field_forbidden(self):
        with self.assertRaises(ValidationError):
            GocryptfsUnmountRequest(
                master_password="StrongMasterKey9",
                other=1,
            )

    def test_master_password_required(self):
        with self.assertRaises(ValidationError) as cm:
            GocryptfsUnmountRequest()

        error = cm.exception.errors()[0]
        self.assertEqual(error["loc"], ("master_password",))
        self.assertEqual(error["type"], "missing")
