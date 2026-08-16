# tests/s3/test_datetime.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.s3.datetime import format_datetime, http_datetime


class TestDatetimeFormat(unittest.TestCase):
    def test_formats_epoch_zero(self):
        self.assertEqual(
            format_datetime(0),
            "1970-01-01T00:00:00.000Z",
        )

    def test_formats_known_timestamp(self):
        self.assertEqual(
            format_datetime(1_704_067_200),
            "2024-01-01T00:00:00.000Z",
        )

    def test_milliseconds_are_always_zero(self):
        self.assertEqual(
            format_datetime(1_704_067_259),
            "2024-01-01T00:00:59.000Z",
        )


class TestDatetimeHttp(unittest.TestCase):
    def test_formats_rfc1123_gmt(self):
        self.assertEqual(
            http_datetime(1_704_067_200),
            "Mon, 01 Jan 2024 00:00:00 GMT",
        )
