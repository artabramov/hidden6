# tests/s3/test_objekt_load.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3ObjektNotFoundError  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.s3.objekt_load import objekt_load  # noqa: E402

load_all_models()


class TestObjektLoad(unittest.IsolatedAsyncioTestCase):
    async def test_returns_objekt(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="cat.png",
            size_bytes=10,
            etag="abc",
            content_type="image/png",
        )
        repo = MagicMock()
        repo.select = AsyncMock(return_value=objekt)

        result = await objekt_load(repo, bucket, "cat.png", "/photos/cat.png")

        self.assertIs(result, objekt)
        repo.select.assert_awaited_once_with(
            Objekt,
            bucket_id=7,
            object_key="cat.png",
        )

    async def test_missing_objekt_raises(self):
        bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjektNotFoundError):
            await objekt_load(repo, bucket, "missing.png", "/photos/missing.png")
