# tests/services/test_multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjektPartInvalidError,
    S3ObjektPartOrderInvalidError,
    S3ObjektPartTooSmallError,
    S3ObjektUploadNotFoundError,
)
from app.hooks import Events  # noqa: E402
from app.locks import LockType  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.user import User  # noqa: E402
from app.schemas.multipart_complete import MultipartPart  # noqa: E402
from app.services.multipart_complete import (  # noqa: E402
    multipart_complete,
)

load_all_models()

PART_HASHES = [
    hashlib.md5(b"first").hexdigest(),
    hashlib.md5(b"second").hexdigest(),
]


def build_multipart_etag(hashes):
    digests = b"".join(bytes.fromhex(value) for value in hashes)
    digest = hashlib.md5(digests).hexdigest()
    return f"{digest}-{len(hashes)}"


class TestMultipartComplete(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(
            f"app.services.multipart_complete.{target}",
            **kwargs,
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )
        self.objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=24,
            etag=build_multipart_etag(PART_HASHES),
            content_type="image/png",
        )

        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        lock_context = AsyncMock()
        lock_context.__aenter__.return_value = None
        lock_context.__aexit__.return_value = None

        self.repo = MagicMock()
        self.repo.delete = AsyncMock()
        self.repo.commit = AsyncMock()
        self.repo.rollback = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch("uuid.uuid4", return_value=MagicMock(hex="staged"))
        self._patch(
            "bucket_load",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.multipart_load = self._patch(
            "multipart_load",
            new_callable=AsyncMock,
            return_value=self.multipart,
        )
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=lock_context,
        )
        self.isfile = self._patch(
            "isfile",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.get_filesize = self._patch(
            "get_filesize",
            new_callable=AsyncMock,
            return_value=1024 * 1024 * 6,
        )
        self.concat = self._patch(
            "concat",
            new_callable=AsyncMock,
            return_value=list(PART_HASHES),
        )
        self._patch(
            "get_mimetype",
            new_callable=AsyncMock,
            return_value="image/png",
        )
        self.bucket_assert = self._patch(
            "bucket_assert",
            new_callable=AsyncMock,
        )
        self.objekt_mkdir = self._patch(
            "objekt_mkdir",
            new_callable=AsyncMock,
        )
        self.objekt_upsert = self._patch(
            "objekt_upsert",
            new_callable=AsyncMock,
            return_value=self.objekt,
        )
        self.rename = self._patch("rename", new_callable=AsyncMock)
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.multipart_cleanup = self._patch(
            "multipart_cleanup",
            new_callable=AsyncMock,
        )
        self.emit = self._patch("hooks.emit", new_callable=AsyncMock)

    def _build_parts(self, hashes=None, numbers=(1, 2)):
        hashes = hashes or PART_HASHES
        return [
            MultipartPart(part_number=number, etag=value)
            for number, value in zip(numbers, hashes)
        ]

    async def _complete(self, parts=None):
        return await multipart_complete(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
            upload_id="beef",
            parts=parts or self._build_parts(),
        )

    async def test_assembles_parts_into_object(self):
        objekt = await self._complete()

        self.concat.assert_awaited_once_with(
            [
                "/mnt/tmp/beef/1.part",
                "/mnt/tmp/beef/2.part",
            ],
            "/mnt/tmp/staged",
        )
        self.lock.assert_called_once_with(
            "/mnt/buckets/photos",
            LockType.WRITE,
        )
        self.rename.assert_awaited_once_with(
            "/mnt/tmp/staged",
            "/mnt/buckets/photos/2024/cat.png",
        )
        self.repo.delete.assert_awaited_once_with(self.multipart)
        self.repo.commit.assert_awaited_once()
        self.assertIs(objekt, self.objekt)
        self.emit.assert_awaited_once_with(
            Events.OBJEKT_UPLOADED,
            objekt,
        )

    async def test_stores_multipart_etag(self):
        await self._complete()

        self.assertEqual(
            self.objekt_upsert.await_args.kwargs["etag"],
            build_multipart_etag(PART_HASHES),
        )

    async def test_removes_staged_parts(self):
        await self._complete()

        self.multipart_cleanup.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_rejects_unordered_parts(self):
        parts = self._build_parts(numbers=(2, 1))

        with self.assertRaises(S3ObjektPartOrderInvalidError):
            await self._complete(parts)

        self.concat.assert_not_awaited()

    async def test_rejects_missing_part(self):
        self.isfile.return_value = False

        with self.assertRaises(S3ObjektPartInvalidError):
            await self._complete()

    async def test_rejects_small_leading_part(self):
        self.get_filesize.return_value = 1024

        with self.assertRaises(S3ObjektPartTooSmallError):
            await self._complete()

    async def test_rejects_mismatched_part_etag(self):
        parts = self._build_parts(
            hashes=[PART_HASHES[0], hashlib.md5(b"other").hexdigest()],
        )

        with self.assertRaises(S3ObjektPartInvalidError):
            await self._complete(parts)

        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/staged")
        self.rename.assert_not_awaited()

    async def test_unknown_upload_raises(self):
        self.multipart_load.side_effect = S3ObjektUploadNotFoundError()

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._complete()

        self.concat.assert_not_awaited()
