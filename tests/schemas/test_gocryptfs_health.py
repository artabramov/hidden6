# tests/schemas/test_gocryptfs_health.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.gocryptfs_health import GocryptfsHealthResponse


class TestGocryptfsHealthResponse(unittest.TestCase):

    def test_accepts_valid_payload(self):
        data = GocryptfsHealthResponse(
            is_cipherdir_created=True,
            is_cipherdir_mounted=False,
            is_watchdog_alive=True,
            unix_timestamp=1715000000,
            timezone_name="UTC",
        )

        self.assertTrue(data.is_cipherdir_created)
        self.assertFalse(data.is_cipherdir_mounted)
        self.assertTrue(data.is_watchdog_alive)
        self.assertEqual(data.unix_timestamp, 1715000000)
        self.assertEqual(data.timezone_name, "UTC")

    def test_rejects_extra_fields(self):
        with self.assertRaises(ValidationError):
            GocryptfsHealthResponse(
                is_cipherdir_created=True,
                is_cipherdir_mounted=True,
                is_watchdog_alive=True,
                unix_timestamp=1,
                timezone_name="UTC",
                extra="nope",
            )

    def test_rejects_missing_fields(self):
        with self.assertRaises(ValidationError):
            GocryptfsHealthResponse(
                is_cipherdir_created=True,
            )
