# tests/services/test_multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3BucketNotFoundError,
    S3ObjektKeyInvalidError,
    S3ObjektPartInvalidError,
    S3ObjektPartOrderInvalidError,
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
        self.log = self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
            content_type="image/png",
        )
        self.objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=24,
            etag="joined-2",
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
        self.multipart_parts = self._patch(
            "multipart_parts",
            new_callable=AsyncMock,
            return_value=(
                [
                    "/mnt/tmp/beef/1.part",
                    "/mnt/tmp/beef/2.part",
                ],
                list(PART_HASHES),
            ),
        )
        self.parts_delete = self._patch(
            "multipart_parts_delete",
            new_callable=AsyncMock,
        )
        self._patch("etag_construct", return_value="joined-2")
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=lock_context,
        )
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.get_filesize = self._patch(
            "get_filesize",
            new_callable=AsyncMock,
            return_value=24,
        )
        self.concat = self._patch(
            "concat",
            new_callable=AsyncMock,
            return_value=list(PART_HASHES),
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
        self.rmtree = self._patch("rmtree", new_callable=AsyncMock)
        self.emit = self._patch("hooks.emit", new_callable=AsyncMock)

    def _build_parts(self, hashes=None, numbers=None):
        hashes = hashes or PART_HASHES
        numbers = numbers or list(range(1, len(hashes) + 1))
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

        self.multipart_parts.assert_awaited_once()
        kwargs = self.multipart_parts.await_args.kwargs
        self.assertIs(kwargs["repo"], self.repo)
        self.assertIs(kwargs["multipart"], self.multipart)
        self.assertEqual(kwargs["upload_dir"], "/mnt/tmp/beef")
        self.concat.assert_awaited_once_with(
            [
                "/mnt/tmp/beef/1.part",
                "/mnt/tmp/beef/2.part",
            ],
            "/mnt/tmp/staged",
        )
        self.assertEqual(
            self.lock.call_args_list,
            [
                call("/mnt/tmp/beef", LockType.WRITE),
                call("/mnt/buckets/photos", LockType.WRITE),
            ],
        )
        self.rename.assert_awaited_once_with(
            "/mnt/tmp/staged",
            "/mnt/buckets/photos/2024/cat.png",
        )
        self.parts_delete.assert_awaited_once_with(
            self.repo,
            self.multipart,
        )
        self.repo.delete.assert_awaited_once_with(self.multipart)
        self.repo.commit.assert_awaited_once()
        self.assertIs(objekt, self.objekt)
        self.emit.assert_awaited_once_with(
            Events.OBJEKT_UPLOADED,
            objekt,
        )

    async def test_concatenates_only_client_listed_parts(self):
        self.multipart_parts.return_value = (
            [
                "/mnt/tmp/beef/1.part",
                "/mnt/tmp/beef/8.part",
            ],
            list(PART_HASHES),
        )

        await self._complete(
            parts=self._build_parts(numbers=[1, 8]),
        )

        self.concat.assert_awaited_once_with(
            [
                "/mnt/tmp/beef/1.part",
                "/mnt/tmp/beef/8.part",
            ],
            "/mnt/tmp/staged",
        )

    async def test_stores_multipart_etag_from_stored_part_etags(self):
        await self._complete()

        self.assertEqual(
            self.objekt_upsert.await_args.kwargs["etag"],
            "joined-2",
        )

    async def test_uses_stored_content_type(self):
        await self._complete()

        self.assertEqual(
            self.objekt_upsert.await_args.kwargs["content_type"],
            "image/png",
        )

    async def test_removes_staged_parts(self):
        await self._complete()

        self.rmtree.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_failed_cleanup_is_logged(self):
        self.rmtree.side_effect = OSError("busy")

        objekt = await self._complete()

        self.log.exception.assert_called_once()
        self.assertIs(objekt, self.objekt)

    async def test_invalid_parts_stop_before_assembly(self):
        self.multipart_parts.side_effect = (
            S3ObjektPartOrderInvalidError()
        )

        with self.assertRaises(S3ObjektPartOrderInvalidError):
            await self._complete()

        self.concat.assert_not_awaited()
        self.parts_delete.assert_not_awaited()

    async def test_missing_bucket_dir_cleans_staged_file(self):
        self.isdir.return_value = False

        with self.assertRaises(S3BucketNotFoundError):
            await self._complete()

        self.rename.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/staged")

    async def test_rejects_mismatched_part_etag(self):
        parts = self._build_parts(
            hashes=[PART_HASHES[0], hashlib.md5(b"other").hexdigest()],
        )

        with self.assertRaises(S3ObjektPartInvalidError):
            await self._complete(parts)

        self.concat.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with("/mnt/tmp/staged")
        self.rename.assert_not_awaited()

    async def test_unknown_upload_raises(self):
        self.multipart_load.side_effect = S3ObjektUploadNotFoundError()

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._complete()

        self.concat.assert_not_awaited()

    async def test_invalid_key_stops_before_assembly(self):
        with self.assertRaises(S3ObjektKeyInvalidError) as cm:
            await multipart_complete(
                bucket_name="photos",
                object_key="../etc/passwd",
                user=self.user,
                session=self.session,
                upload_id="beef",
                parts=self._build_parts(),
            )

        self.assertEqual(cm.exception.resource, "/photos/../etc/passwd")
        self.multipart_load.assert_not_awaited()
        self.concat.assert_not_awaited()
