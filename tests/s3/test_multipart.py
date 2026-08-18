# tests/s3/test_multipart.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjectPartInvalidError,
    S3ObjectPartNumberInvalidError,
    S3ObjectPartOrderInvalidError,
    S3ObjectPartTooSmallError,
    S3ObjectUploadNotFoundError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.objekt_multipart_part import ObjektMultipartPart  # noqa: E402
from app.s3.multipart import (  # noqa: E402
    load_multipart,
    upsert_multipart_part,
    load_multipart_parts,
    delete_multipart_parts,
    list_multipart_parts,
)
from app.schemas.multipart_complete import MultipartPart  # noqa: E402

load_all_models()


class TestLoadMultipart(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )
        self.repo = MagicMock()
        self.repo.select = AsyncMock(return_value=self.multipart)

    async def _load(self):
        return await load_multipart(
            repo=self.repo,
            bucket=self.bucket,
            object_key="2024/cat.png",
            upload_id="beef",
            resource="/photos/2024/cat.png",
        )

    async def test_returns_upload_of_the_addressed_key(self):
        multipart = await self._load()

        self.assertIs(multipart, self.multipart)

    async def test_unknown_upload_raises(self):
        self.repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjectUploadNotFoundError):
            await self._load()

    async def test_upload_of_another_bucket_raises(self):
        self.multipart.bucket_id = 99

        with self.assertRaises(S3ObjectUploadNotFoundError):
            await self._load()

    async def test_upload_of_another_key_raises(self):
        self.multipart.object_key = "other.png"

        with self.assertRaises(S3ObjectUploadNotFoundError):
            await self._load()


class TestUpsertMultipartPart(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )
        self.repo = MagicMock()
        self.repo.select = AsyncMock(return_value=None)
        self.repo.insert = AsyncMock(side_effect=lambda obj, **kwargs: obj)
        self.repo.update = AsyncMock(side_effect=lambda obj, **kwargs: obj)
        self.repo.commit = AsyncMock()

    async def test_inserts_new_part_row(self):
        row = await upsert_multipart_part(
            repo=self.repo,
            multipart=self.multipart,
            part_number=1,
            size_bytes=1024,
            etag="abc",
        )

        self.repo.insert.assert_awaited_once()
        self.assertEqual(row.objekt_multipart_id, 5)
        self.assertEqual(row.part_number, 1)
        self.assertEqual(row.size_bytes, 1024)
        self.assertEqual(row.etag, "abc")
        self.assertNotIn("commit", self.repo.insert.await_args.kwargs)
        self.repo.commit.assert_not_called()
        self.repo.update.assert_not_awaited()

    async def test_updates_existing_part_row(self):
        existing = ObjektMultipartPart(
            id=9,
            objekt_multipart_id=5,
            part_number=1,
            size_bytes=10,
            etag="old",
            modified_at=1,
        )
        self.repo.select = AsyncMock(return_value=existing)

        with patch("app.s3.multipart.time.time", return_value=2_000_000):
            row = await upsert_multipart_part(
                repo=self.repo,
                multipart=self.multipart,
                part_number=1,
                size_bytes=2048,
                etag="new",
            )

        self.repo.insert.assert_not_awaited()
        self.repo.update.assert_awaited_once_with(existing)
        self.repo.commit.assert_not_called()
        self.assertIs(row, existing)
        self.assertEqual(existing.size_bytes, 2048)
        self.assertEqual(existing.etag, "new")
        self.assertEqual(existing.modified_at, 2_000_000)


class TestListMultipartParts(unittest.IsolatedAsyncioTestCase):
    async def test_lists_parts_ordered_with_pagination(self):
        multipart = ObjektMultipart(id=5, upload_id="beef", object_key="a")
        repo = MagicMock()
        repo.select_all = AsyncMock(return_value=[])

        await list_multipart_parts(
            repo,
            multipart,
            part_number_marker=2,
            max_parts=1000,
        )

        repo.select_all.assert_awaited_once_with(
            ObjektMultipartPart,
            objekt_multipart_id=5,
            order_by="part_number",
            order="asc",
            part_number__gt=2,
            limit=1000,
        )


class TestDeleteMultipartParts(unittest.IsolatedAsyncioTestCase):
    async def test_deletes_every_part_row(self):
        multipart = ObjektMultipart(id=5, upload_id="beef", object_key="a")
        rows = [
            ObjektMultipartPart(id=1, part_number=1),
            ObjektMultipartPart(id=2, part_number=3),
        ]
        repo = MagicMock()
        repo.select_all = AsyncMock(return_value=rows)
        repo.delete = AsyncMock()
        repo.flush = AsyncMock()

        await delete_multipart_parts(repo, multipart)

        self.assertEqual(repo.delete.await_count, 2)
        repo.delete.assert_any_await(rows[0], flush=False)
        repo.delete.assert_any_await(rows[1], flush=False)
        repo.flush.assert_awaited_once()


class TestLoadMultipartParts(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(f"app.s3.multipart.{target}", **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )
        self.repo = MagicMock()
        self.isfile = self._patch(
            "isfile",
            new_callable=AsyncMock,
            return_value=True,
        )

        async def _select(_cls, **filters):
            number = filters["part_number"]
            return ObjektMultipartPart(
                id=number,
                objekt_multipart_id=5,
                part_number=number,
                size_bytes=1024 * 1024 * 6,
                etag=f"etag-{number}",
            )

        self.repo.select = AsyncMock(side_effect=_select)

    def _build_parts(self, numbers, etags=None):
        etags = etags or [f"etag-{number}" for number in numbers]
        return [
            MultipartPart(part_number=number, etag=etag)
            for number, etag in zip(numbers, etags)
        ]

    async def _load(self, numbers=(1, 2)):
        return await load_multipart_parts(
            repo=self.repo,
            multipart=self.multipart,
            upload_path="/mnt/tmp/beef",
            parts=self._build_parts(numbers),
            resource="/photos/2024/cat.png",
        )

    async def test_maps_parts_onto_rows_and_staged_files(self):
        paths, etags = await self._load()

        self.assertEqual(
            paths,
            ["/mnt/tmp/beef/1.part", "/mnt/tmp/beef/2.part"],
        )
        self.assertEqual(etags, ["etag-1", "etag-2"])
        self.assertEqual(self.repo.select.await_count, 2)
        self.isfile.assert_any_await("/mnt/tmp/beef/1.part")
        self.isfile.assert_any_await("/mnt/tmp/beef/2.part")

    async def test_accepts_noncontiguous_ascending_parts(self):
        paths, etags = await self._load(numbers=(1, 3, 8))

        self.assertEqual(
            paths,
            [
                "/mnt/tmp/beef/1.part",
                "/mnt/tmp/beef/3.part",
                "/mnt/tmp/beef/8.part",
            ],
        )
        self.assertEqual(etags, ["etag-1", "etag-3", "etag-8"])

    async def test_rejects_unordered_parts(self):
        with self.assertRaises(S3ObjectPartOrderInvalidError):
            await self._load(numbers=(2, 1))

        self.repo.select.assert_awaited_once()

    async def test_rejects_repeated_part(self):
        with self.assertRaises(S3ObjectPartOrderInvalidError):
            await self._load(numbers=(1, 1))

        self.repo.select.assert_awaited_once()

    async def test_rejects_part_number_above_maximum(self):
        with self.assertRaises(S3ObjectPartNumberInvalidError):
            await self._load(numbers=(10001,))

        self.repo.select.assert_not_awaited()

    async def test_rejects_missing_part_row(self):
        self.repo.select = AsyncMock(return_value=None)

        with self.assertRaises(S3ObjectPartInvalidError):
            await self._load()

        self.isfile.assert_not_awaited()

    async def test_rejects_missing_staged_file(self):
        self.isfile.return_value = False

        with self.assertRaises(S3ObjectPartInvalidError):
            await self._load()

    async def test_rejects_small_non_final_part(self):
        async def _select(_cls, **filters):
            number = filters["part_number"]
            return ObjektMultipartPart(
                id=number,
                objekt_multipart_id=5,
                part_number=number,
                size_bytes=1024,
                etag=f"etag-{number}",
            )

        self.repo.select = AsyncMock(side_effect=_select)

        with self.assertRaises(S3ObjectPartTooSmallError):
            await self._load()

        # Size is checked inline, so the next part is never loaded.
        self.repo.select.assert_awaited_once()

    async def test_last_part_may_be_small(self):
        async def _select(_cls, **filters):
            return ObjektMultipartPart(
                id=1,
                objekt_multipart_id=5,
                part_number=1,
                size_bytes=1024,
                etag="etag-1",
            )

        self.repo.select = AsyncMock(side_effect=_select)

        paths, etags = await self._load(numbers=(1,))

        self.assertEqual(paths, ["/mnt/tmp/beef/1.part"])
        self.assertEqual(etags, ["etag-1"])

    async def test_small_non_final_part_rejected_with_large_final(self):
        async def _select(_cls, **filters):
            number = filters["part_number"]
            size = 1024 if number == 1 else 1024 * 1024 * 6
            return ObjektMultipartPart(
                id=number,
                objekt_multipart_id=5,
                part_number=number,
                size_bytes=size,
                etag=f"etag-{number}",
            )

        self.repo.select = AsyncMock(side_effect=_select)

        with self.assertRaises(S3ObjectPartTooSmallError):
            await self._load(numbers=(1, 2))

        self.repo.select.assert_awaited_once()
