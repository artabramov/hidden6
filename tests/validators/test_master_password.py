# tests/validators/test_master_password.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.validators.master_password import validate_master_password


class TestValidateMasterPassword(unittest.TestCase):
    def test_rejects_missing_lowercase(self):
        with self.assertRaises(ValueError):
            validate_master_password("PASSWORD123")

    def test_rejects_missing_uppercase(self):
        with self.assertRaises(ValueError):
            validate_master_password("password123")

    def test_rejects_missing_digit(self):
        with self.assertRaises(ValueError):
            validate_master_password("Password")

    def test_accepts_valid_password(self):
        value = "StrongMasterPass9"

        result = validate_master_password(value)

        self.assertEqual(result, value)
