# tests/s3/test_objekt_upsert.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.s3.objekt_upsert import objekt_upsert  # noqa: E402

load_all_models()


class TestObjektUpsert(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=1, username="alice", is_root=False)
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")

    def _build_repo(self, existing):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=existing)
        repo.insert = AsyncMock(side_effect=lambda obj: obj)
        repo.update = AsyncMock(side_effect=lambda obj: obj)
        return repo

    async def _upsert(self, repo):
        return await objekt_upsert(
            repo=repo,
            bucket=self.bucket,
            user=self.user,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
        )

    async def test_inserts_new_objekt(self):
        repo = self._build_repo(None)

        objekt = await self._upsert(repo)

        repo.insert.assert_awaited_once_with(objekt)
        self.assertIsInstance(objekt, Objekt)
        self.assertEqual(objekt.bucket_id, 7)
        self.assertEqual(objekt.user_id, 1)
        self.assertEqual(objekt.object_key, "2024/cat.png")
        self.assertEqual(objekt.size_bytes, 12)
        self.assertEqual(objekt.etag, "etag123")
        self.assertEqual(objekt.content_type, "image/png")

    async def test_updates_existing_objekt(self):
        existing = Objekt(
            id=3,
            bucket_id=7,
            user_id=99,
            object_key="2024/cat.png",
            size_bytes=1,
            etag="old",
            content_type="text/plain",
        )
        repo = self._build_repo(existing)

        objekt = await self._upsert(repo)

        self.assertIs(objekt, existing)
        repo.insert.assert_not_awaited()
        repo.update.assert_awaited_once_with(existing)
        self.assertEqual(existing.user_id, 1)
        self.assertEqual(existing.size_bytes, 12)
        self.assertEqual(existing.etag, "etag123")
        self.assertEqual(existing.content_type, "image/png")
