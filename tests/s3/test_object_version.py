# tests/s3/test_object_version.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, call

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.models.object import S3Object  # noqa: E402
from app.models.object_metadata import S3ObjectMetadata  # noqa: E402
from app.models.object_tag import S3ObjectTag  # noqa: E402
from app.models.object_version import S3ObjectVersion  # noqa: E402
from app.models.object_version_metadata import S3ObjectVersionMetadata  # noqa: E402
from app.models.object_version_tag import S3ObjectVersionTag  # noqa: E402
from app.s3.object_version import create_object_version  # noqa: E402

load_all_models()


class TestCreateObjectVersion(unittest.IsolatedAsyncioTestCase):
    def _build_repo(self, *, metadata=None, tags=None):
        metadata = metadata or []
        tags = tags or []
        repo = MagicMock()

        async def _insert(obj, flush=True, commit=False):
            if isinstance(obj, S3ObjectVersion):
                obj.id = 42
            return obj

        async def _select_all(cls, **kwargs):
            if cls is S3ObjectMetadata:
                return metadata
            if cls is S3ObjectTag:
                return tags
            return []

        repo.insert = AsyncMock(side_effect=_insert)
        repo.select_all = AsyncMock(side_effect=_select_all)
        repo.flush = AsyncMock()
        return repo

    def _s3_object(self, **kwargs) -> S3Object:
        defaults = {
            "id": 3,
            "bucket_id": 7,
            "user_id": 1,
            "object_key": "2024/cat.png",
            "modified_at": 1_704_067_200,
            "size_bytes": 12,
            "etag": "etag123",
            "content_type": "image/png",
            "version_uuid": "a" * 32,
            "delete_marker": False,
            "lock_mode": None,
            "retain_until": None,
            "legal_hold": False,
        }
        defaults.update(kwargs)
        return S3Object(**defaults)

    async def test_preserves_current_object_state(self):
        s3_object = self._s3_object(
            lock_mode="COMPLIANCE",
            retain_until=1_704_153_600,
            legal_hold=True,
        )
        repo = self._build_repo()

        version = await create_object_version(repo, s3_object)

        self.assertIsInstance(version, S3ObjectVersion)
        self.assertEqual(version.object_id, 3)
        self.assertEqual(version.user_id, 1)
        self.assertEqual(version.modified_at, 1_704_067_200)
        self.assertEqual(version.version_uuid, "a" * 32)
        self.assertEqual(version.size_bytes, 12)
        self.assertEqual(version.etag, "etag123")
        self.assertEqual(version.content_type, "image/png")
        self.assertFalse(version.delete_marker)
        self.assertEqual(version.lock_mode, "COMPLIANCE")
        self.assertEqual(version.retain_until, 1_704_153_600)
        self.assertTrue(version.legal_hold)
        repo.select_all.assert_has_awaits(
            [
                call(S3ObjectMetadata, object_id=3),
                call(S3ObjectTag, object_id=3),
            ],
        )
        repo.flush.assert_awaited_once_with()

    async def test_preserves_null_version_uuid(self):
        s3_object = self._s3_object(version_uuid=None)
        repo = self._build_repo()

        version = await create_object_version(repo, s3_object)

        self.assertIsNone(version.version_uuid)

    async def test_preserves_delete_marker(self):
        s3_object = self._s3_object(
            version_uuid="d" * 32,
            delete_marker=True,
            size_bytes=None,
            etag=None,
            content_type=None,
        )
        repo = self._build_repo()

        version = await create_object_version(repo, s3_object)

        self.assertTrue(version.delete_marker)
        self.assertIsNone(version.size_bytes)
        self.assertIsNone(version.etag)
        self.assertIsNone(version.content_type)

    async def test_copies_metadata_and_tags(self):
        s3_object = self._s3_object()
        metadata = S3ObjectMetadata(
            id=11,
            object_id=3,
            meta_key="x-amz-meta-owner",
            meta_value="alice",
        )
        tag = S3ObjectTag(
            id=12,
            object_id=3,
            tag_key="env",
            tag_value="prod",
        )
        repo = self._build_repo(metadata=[metadata], tags=[tag])

        version = await create_object_version(repo, s3_object)

        self.assertEqual(version.id, 42)
        self.assertEqual(repo.insert.await_count, 3)
        version_row = repo.insert.await_args_list[0].args[0]
        self.assertIsInstance(version_row, S3ObjectVersion)
        self.assertEqual(version_row.object_id, 3)

        metadata_call = repo.insert.await_args_list[1]
        self.assertEqual(metadata_call.kwargs, {"flush": False})
        metadata_row = metadata_call.args[0]
        self.assertIsInstance(metadata_row, S3ObjectVersionMetadata)
        self.assertEqual(metadata_row.object_version_id, 42)
        self.assertEqual(metadata_row.meta_key, "x-amz-meta-owner")
        self.assertEqual(metadata_row.meta_value, "alice")

        tag_call = repo.insert.await_args_list[2]
        self.assertEqual(tag_call.kwargs, {"flush": False})
        tag_row = tag_call.args[0]
        self.assertIsInstance(tag_row, S3ObjectVersionTag)
        self.assertEqual(tag_row.object_version_id, 42)
        self.assertEqual(tag_row.tag_key, "env")
        self.assertEqual(tag_row.tag_value, "prod")
        repo.flush.assert_awaited_once_with()
