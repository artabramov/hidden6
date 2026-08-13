# tests/s3/test_datetime_http.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from app.s3.datetime_http import datetime_http


class TestDatetimeHttp(unittest.TestCase):
    def test_formats_rfc1123_gmt(self):
        self.assertEqual(
            datetime_http(1_704_067_200),
            "Mon, 01 Jan 2024 00:00:00 GMT",
        )
