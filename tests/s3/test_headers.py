# tests/s3/test_headers.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.s3.datetime import http_datetime  # noqa: E402
from app.s3.headers import objekt_headers  # noqa: E402

load_all_models()


class TestObjektHeaders(unittest.TestCase):
    def test_builds_get_and_head_headers(self):
        objekt = Objekt(
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
            objekt_headers(objekt),
            {
                "Content-Length": "12",
                "ETag": '"etag123"',
                "Last-Modified": http_datetime(1_704_067_200),
            },
        )
