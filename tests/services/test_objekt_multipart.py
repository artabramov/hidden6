# tests/services/test_objekt_multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjektPartInvalidError,
    S3ObjektPartNumberInvalidError,
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
from app.schemas.objekt_multipart import MultipartPart  # noqa: E402
from app.services.objekt_multipart import (  # noqa: E402
    multipart_abort,
    multipart_complete,
    multipart_create,
    multipart_upload,
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


class MultipartTestCase(unittest.IsolatedAsyncioTestCase):
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

        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        self.repo = MagicMock()
        self.repo.select = AsyncMock(return_value=self.multipart)
        self.repo.insert = AsyncMock(side_effect=lambda obj, **kw: obj)
        self.repo.delete = AsyncMock()
        self.repo.commit = AsyncMock()
        self.repo.rollback = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch("uuid.uuid4", return_value=MagicMock(hex="beef"))
        self.load_bucket = self._patch(
            "load_bucket",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.mkdir = self._patch("mkdir", new_callable=AsyncMock)
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.rmdir = self._patch("rmdir", new_callable=AsyncMock)
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.listdir = self._patch(
            "listdir",
            new_callable=AsyncMock,
            return_value=["part.00001"],
        )

    def _patch(self, target, **kwargs):
        patcher = patch(
            f"app.services.objekt_multipart.{target}",
            **kwargs,
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _build_lock_context(self):
        ctx = AsyncMock()
        ctx.__aenter__.return_value = None
        ctx.__aexit__.return_value = None
        return ctx


class TestMultipartCreate(MultipartTestCase):
    async def _create(self):
        return await multipart_create(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
        )

    async def test_registers_upload_and_stages_dir(self):
        multipart = await self._create()

        self.mkdir.assert_awaited_once_with("/mnt/tmp/beef")
        self.repo.insert.assert_awaited_once()
        self.assertEqual(multipart.upload_id, "beef")
        self.assertEqual(multipart.bucket_id, 7)
        self.assertEqual(multipart.user_id, 1)
        self.assertEqual(multipart.object_key, "2024/cat.png")
        self.assertEqual(
            self.repo.insert.await_args.kwargs["commit"],
            True,
        )

    async def test_failed_insert_removes_staged_dir(self):
        self.repo.insert.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._create()

        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with(
            "/mnt/tmp/beef/part.00001",
        )
        self.rmdir.assert_awaited_once_with("/mnt/tmp/beef")


class TestMultipartUpload(MultipartTestCase):
    def setUp(self):
        super().setUp()
        self.lock = self._patch(
            "locks.lock_file",
            return_value=self._build_lock_context(),
        )
        self.upload = self._patch("upload", new_callable=AsyncMock)
        self._patch(
            "get_file_hash",
            new_callable=AsyncMock,
            return_value=PART_HASHES[0],
        )

    async def _upload(self, part_number=1):
        return await multipart_upload(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
            upload_id="beef",
            part_number=part_number,
            body=MagicMock(),
        )

    async def test_stores_part_and_returns_etag(self):
        etag = await self._upload()

        part_path = "/mnt/tmp/beef/part.00001"
        self.upload.assert_awaited_once()
        self.assertEqual(self.upload.await_args.args[1], part_path)
        self.lock.assert_called_once_with(part_path, LockType.WRITE)
        self.assertEqual(etag, PART_HASHES[0])

    async def test_rejects_part_number_out_of_range(self):
        with self.assertRaises(S3ObjektPartNumberInvalidError):
            await self._upload(part_number=0)

        with self.assertRaises(S3ObjektPartNumberInvalidError):
            await self._upload(part_number=10001)

        self.upload.assert_not_awaited()

    async def test_unknown_upload_raises(self):
        self.repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._upload()

    async def test_upload_of_another_key_raises(self):
        self.multipart.object_key = "other.png"

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._upload()

    async def test_missing_upload_dir_raises(self):
        self.isdir.return_value = False

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._upload()

    async def test_failed_upload_keeps_the_stored_part(self):
        self.upload.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.delete.assert_not_awaited()


class TestMultipartComplete(MultipartTestCase):
    def setUp(self):
        super().setUp()
        self.objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=24,
            etag=build_multipart_etag(PART_HASHES),
            content_type="image/png",
        )
        self._patch(
            "uuid.uuid4",
            return_value=MagicMock(hex="staged"),
        )
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=self._build_lock_context(),
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
        self.assert_bucket_dir = self._patch(
            "assert_bucket_dir",
            new_callable=AsyncMock,
        )
        self.mkdir_object_parent = self._patch(
            "mkdir_object_parent",
            new_callable=AsyncMock,
        )
        self.upsert_objekt = self._patch(
            "upsert_objekt",
            new_callable=AsyncMock,
            return_value=self.objekt,
        )
        self.rename = self._patch("rename", new_callable=AsyncMock)
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
                "/mnt/tmp/beef/part.00001",
                "/mnt/tmp/beef/part.00002",
            ],
            "/mnt/tmp/staged",
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
            self.upsert_objekt.await_args.kwargs["etag"],
            build_multipart_etag(PART_HASHES),
        )

    async def test_removes_staged_parts(self):
        await self._complete()

        self.delete.assert_awaited_once_with(
            "/mnt/tmp/beef/part.00001",
        )
        self.rmdir.assert_awaited_once_with("/mnt/tmp/beef")

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
        self.repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._complete()


class TestMultipartAbort(MultipartTestCase):
    async def _abort(self):
        await multipart_abort(
            bucket_name="photos",
            object_key="2024/cat.png",
            user=self.user,
            session=self.session,
            upload_id="beef",
        )

    async def test_drops_upload_and_staged_parts(self):
        await self._abort()

        self.repo.delete.assert_awaited_once_with(
            self.multipart,
            commit=True,
        )
        self.delete.assert_awaited_once_with(
            "/mnt/tmp/beef/part.00001",
        )
        self.rmdir.assert_awaited_once_with("/mnt/tmp/beef")

    async def test_unknown_upload_raises(self):
        self.repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._abort()

    async def test_upload_of_another_bucket_raises(self):
        self.multipart.bucket_id = 99

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._abort()
