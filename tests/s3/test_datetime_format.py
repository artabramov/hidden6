# tests/s3/test_datetime_format.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.s3.datetime_format import datetime_format


class TestDatetimeFormat(unittest.TestCase):
    def test_format_epoch(self):
        self.assertEqual(
            datetime_format(0),
            "1970-01-01T00:00:00.000Z",
        )

    def test_format_utc_midnight(self):
        self.assertEqual(
            datetime_format(1_704_067_200),
            "2024-01-01T00:00:00.000Z",
        )

    def test_format_keeps_seconds(self):
        self.assertEqual(
            datetime_format(1_704_067_259),
            "2024-01-01T00:00:59.000Z",
        )
