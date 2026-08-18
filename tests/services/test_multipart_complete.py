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
    S3ObjectKeyConflictError,
    S3ObjectKeyInvalidError,
    S3ObjectPartInvalidError,
    S3ObjectPartOrderInvalidError,
    S3ObjectUploadNotFoundError,
)
from app.hooks import Events  # noqa: E402
from app.locks import LockType  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.object import S3Object  # noqa: E402
from app.models.object_multipart import ObjectMultipart  # noqa: E402
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

BUCKET_PATH = "/mnt/buckets/photos"
OBJECT_PATH = "/mnt/buckets/photos/2024/cat.png"
UPLOAD_PATH = "/mnt/tmp/beef"
STAGED_PATH = "/mnt/tmp/staged"
CLEANUP_PATH = "/mnt/tmp/.beef.completed.done"
BACKUP_PATH = "/mnt/tmp/.bakhex.object.bak"


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
        self.multipart = ObjectMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
            content_type="image/png",
        )
        self.objekt = S3Object(
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
        self._patch(
            "uuid.uuid4",
            side_effect=[
                MagicMock(hex="staged"),
                MagicMock(hex="done"),
                MagicMock(hex="bakhex"),
            ],
        )
        self._patch(
            "load_bucket",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.load_multipart = self._patch(
            "load_multipart",
            new_callable=AsyncMock,
            return_value=self.multipart,
        )
        self.load_multipart_parts = self._patch(
            "load_multipart_parts",
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
            "delete_multipart_parts",
            new_callable=AsyncMock,
        )
        self._patch("construct_etag", return_value="joined-2")
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=lock_context,
        )
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.isfile = self._patch(
            "isfile",
            new_callable=AsyncMock,
            return_value=False,
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
        self.object_mkdir = self._patch(
            "object_mkdir",
            new_callable=AsyncMock,
        )
        self.upsert_object = self._patch(
            "upsert_object",
            new_callable=AsyncMock,
            return_value=self.objekt,
        )
        self.copy = self._patch("copy", new_callable=AsyncMock)
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
            session=self.session,
            current_user=self.user,
            bucket_name="photos",
            object_key="2024/cat.png",
            upload_id="beef",
            parts=parts or self._build_parts(),
        )

    def _delete_paths(self):
        return [c.args[0] for c in self.delete.await_args_list]

    async def test_assembles_parts_into_object(self):
        objekt = await self._complete()

        self.load_multipart_parts.assert_awaited_once()
        self.concat.assert_awaited_once_with(
            [
                "/mnt/tmp/beef/1.part",
                "/mnt/tmp/beef/2.part",
            ],
            STAGED_PATH,
        )
        self.assertEqual(
            self.lock.call_args_list,
            [
                call(UPLOAD_PATH, LockType.WRITE),
                call(BUCKET_PATH, LockType.WRITE),
            ],
        )
        self.copy.assert_not_awaited()
        self.assertEqual(
            self.rename.await_args_list,
            [
                call(STAGED_PATH, OBJECT_PATH),
                call(UPLOAD_PATH, CLEANUP_PATH),
            ],
        )
        self.parts_delete.assert_awaited_once_with(
            self.repo,
            self.multipart,
        )
        self.repo.delete.assert_awaited_once_with(self.multipart)
        self.repo.commit.assert_awaited_once()
        self.rmtree.assert_awaited_once_with(CLEANUP_PATH)
        self.delete.assert_not_awaited()
        self.assertIs(objekt, self.objekt)
        self.emit.assert_awaited_once_with(
            Events.OBJECT_UPLOADED,
            objekt,
        )

    async def test_existing_object_backed_up_until_commit(self):
        self.isfile.return_value = True

        await self._complete()

        self.copy.assert_awaited_once_with(OBJECT_PATH, BACKUP_PATH)
        self.assertEqual(
            self.rename.await_args_list,
            [
                call(STAGED_PATH, OBJECT_PATH),
                call(UPLOAD_PATH, CLEANUP_PATH),
            ],
        )
        self.delete.assert_awaited_once_with(BACKUP_PATH)
        self.rmtree.assert_awaited_once_with(CLEANUP_PATH)

    async def test_holds_multipart_lock_across_commit(self):
        hold = {"multipart": False, "bucket": False}
        events = []

        class MultipartLock:
            async def __aenter__(self):
                hold["multipart"] = True
                events.append("multipart_enter")
                return None

            async def __aexit__(self, *args):
                hold["multipart"] = False
                events.append("multipart_exit")
                return None

        class BucketLock:
            async def __aenter__(self):
                hold["bucket"] = True
                events.append("bucket_enter")
                if not hold["multipart"]:
                    raise AssertionError("multipart lock released early")
                return None

            async def __aexit__(self, *args):
                hold["bucket"] = False
                events.append("bucket_exit")
                if not hold["multipart"]:
                    raise AssertionError("multipart lock released early")
                return None

        def _lock(path, _type):
            if path == UPLOAD_PATH:
                return MultipartLock()
            return BucketLock()

        self.lock.side_effect = _lock

        async def _commit():
            events.append("commit")
            if not hold["multipart"] or not hold["bucket"]:
                raise AssertionError("locks released before commit")

        self.repo.commit = AsyncMock(side_effect=_commit)

        await self._complete()

        self.assertEqual(
            events,
            [
                "multipart_enter",
                "bucket_enter",
                "commit",
                "bucket_exit",
                "multipart_exit",
            ],
        )

    async def test_concatenates_only_client_listed_parts(self):
        self.load_multipart_parts.return_value = (
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
            STAGED_PATH,
        )

    async def test_rejects_corrupted_staged_part_hash(self):
        self.concat.return_value = [
            PART_HASHES[0],
            hashlib.md5(b"corrupt").hexdigest(),
        ]

        with self.assertRaises(S3ObjectPartInvalidError):
            await self._complete()

        self.upsert_object.assert_not_awaited()
        self.parts_delete.assert_not_awaited()
        self.repo.commit.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_stores_multipart_etag_from_stored_part_etags(self):
        await self._complete()

        self.assertEqual(
            self.upsert_object.await_args.kwargs["etag"],
            "joined-2",
        )

    async def test_uses_stored_content_type(self):
        await self._complete()

        self.assertEqual(
            self.upsert_object.await_args.kwargs["content_type"],
            "image/png",
        )

    async def test_rejects_mismatched_client_etag(self):
        parts = self._build_parts(
            hashes=[PART_HASHES[0], hashlib.md5(b"other").hexdigest()],
        )

        with self.assertRaises(S3ObjectPartInvalidError):
            await self._complete(parts)

        self.concat.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_invalid_parts_stop_before_assembly(self):
        self.load_multipart_parts.side_effect = (
            S3ObjectPartOrderInvalidError()
        )

        with self.assertRaises(S3ObjectPartOrderInvalidError):
            await self._complete()

        self.concat.assert_not_awaited()
        self.parts_delete.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_unknown_upload_raises(self):
        self.load_multipart.side_effect = S3ObjectUploadNotFoundError()

        with self.assertRaises(S3ObjectUploadNotFoundError):
            await self._complete()

        self.concat.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_invalid_key_stops_before_assembly(self):
        with self.assertRaises(S3ObjectKeyInvalidError) as cm:
            await multipart_complete(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                object_key="../etc/passwd",
                upload_id="beef",
                parts=self._build_parts(),
            )

        self.assertEqual(cm.exception.resource, "/photos/../etc/passwd")
        self.load_multipart.assert_not_awaited()
        self.concat.assert_not_awaited()

    async def test_missing_bucket_dir_cleans_staged_file(self):
        self.isdir.return_value = False

        with self.assertRaises(S3BucketNotFoundError):
            await self._complete()

        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with(STAGED_PATH)
        self.parts_delete.assert_not_awaited()
        self.rename.assert_not_awaited()

    async def test_directory_at_object_path_is_a_key_conflict(self):
        self.rename.side_effect = IsADirectoryError()

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._complete()

        self.repo.commit.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_commit_failure_deletes_published_new_object(self):
        self.repo.commit.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._complete()

        self.repo.rollback.assert_awaited_once()
        self.assertEqual(
            self.rename.await_args_list,
            [
                call(STAGED_PATH, OBJECT_PATH),
                call(UPLOAD_PATH, CLEANUP_PATH),
                call(CLEANUP_PATH, UPLOAD_PATH),
            ],
        )
        self.assertEqual(
            self._delete_paths(),
            [OBJECT_PATH, STAGED_PATH],
        )
        self.rmtree.assert_not_awaited()
        self.emit.assert_not_awaited()

    async def test_commit_failure_restores_overwritten_object(self):
        self.isfile.return_value = True
        self.repo.commit.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._complete()

        self.assertEqual(
            self.copy.await_args_list,
            [
                call(OBJECT_PATH, BACKUP_PATH),
                call(BACKUP_PATH, OBJECT_PATH),
            ],
        )
        self.assertEqual(
            self.rename.await_args_list,
            [
                call(STAGED_PATH, OBJECT_PATH),
                call(UPLOAD_PATH, CLEANUP_PATH),
                call(CLEANUP_PATH, UPLOAD_PATH),
            ],
        )
        self.assertEqual(
            self._delete_paths(),
            [BACKUP_PATH, STAGED_PATH],
        )
        self.rmtree.assert_not_awaited()

    async def test_rename_conflict_discards_backup_when_object_existed(self):
        self.isfile.return_value = True
        self.rename.side_effect = IsADirectoryError()

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._complete()

        self.copy.assert_awaited_once_with(OBJECT_PATH, BACKUP_PATH)
        self.assertEqual(
            self._delete_paths(),
            [BACKUP_PATH, STAGED_PATH],
        )
        self.rmtree.assert_not_awaited()

    async def test_logs_when_post_commit_cleanup_fails(self):
        self.rmtree.side_effect = OSError("busy")

        objekt = await self._complete()

        self.assertIs(objekt, self.objekt)
        self.repo.commit.assert_awaited_once()
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "cleanup_path=%s",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_post_commit_backup_cleanup_fails(self):
        self.isfile.return_value = True
        self.delete.side_effect = OSError("busy")

        objekt = await self._complete()

        self.assertIs(objekt, self.objekt)
        self.emit.assert_awaited_once()
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "backup_path=%s",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_object_restore_fails(self):
        self.isfile.return_value = True
        self.repo.commit.side_effect = RuntimeError("db down")
        self.copy.side_effect = [None, OSError("busy")]

        with self.assertRaises(RuntimeError):
            await self._complete()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertTrue(
            any("msg=restore_failed" in message for message in messages),
        )
        self.assertEqual(
            self.rename.await_args_list[-1],
            call(CLEANUP_PATH, UPLOAD_PATH),
        )

    async def test_logs_when_upload_restore_fails(self):
        self.repo.commit.side_effect = RuntimeError("db down")
        self.rename.side_effect = [
            None,
            None,
            OSError("busy"),
        ]

        with self.assertRaises(RuntimeError):
            await self._complete()

        self.delete.assert_any_await(OBJECT_PATH)
        self.assertIn(
            "msg=restore_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "cleanup_path=%s",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_published_cleanup_fails(self):
        self.repo.commit.side_effect = RuntimeError("db down")
        self.delete.side_effect = [OSError("busy"), None]

        with self.assertRaises(RuntimeError):
            await self._complete()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertTrue(
            any("object_path=%s" in message for message in messages),
        )

    async def test_logs_when_assembly_rollback_fails(self):
        self.concat.side_effect = RuntimeError("disk full")
        self.repo.rollback.side_effect = RuntimeError("session closed")

        with self.assertRaises(RuntimeError) as cm:
            await self._complete()

        self.assertEqual(str(cm.exception), "disk full")
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args_list[0].args[0],
        )
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_logs_when_staged_cleanup_fails_during_assembly(self):
        self.concat.side_effect = RuntimeError("disk full")
        self.delete.side_effect = OSError("busy")

        with self.assertRaises(RuntimeError):
            await self._complete()

        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "staged_path=%s",
            self.log.exception.call_args.args[0],
        )
