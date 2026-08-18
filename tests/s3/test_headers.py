# tests/s3/test_headers.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.models.object import S3Object  # noqa: E402
from app.s3.datetime import http_datetime  # noqa: E402
from app.s3.headers import etag_headers, object_headers  # noqa: E402

load_all_models()


class TestEtagHeaders(unittest.TestCase):
    def test_quotes_etag_value(self):
        self.assertEqual(
            etag_headers("etag123"),
            {"ETag": '"etag123"'},
        )


class TestObjectHeaders(unittest.TestCase):
    def test_builds_get_and_head_headers(self):
        s3_object = S3Object(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
            modified_at=1_704_067_200,
        )

        self.assertEqual(
            object_headers(s3_object),
            {
                "Content-Length": "12",
                "ETag": '"etag123"',
                "Last-Modified": http_datetime(1_704_067_200),
            },
        )
