# tests/services/test_multipart_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3ObjektKeyInvalidError,
    S3ObjektPartNumberInvalidError,
    S3ObjektUploadNotFoundError,
)
from app.locks import LockType  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.multipart_upload import multipart_upload  # noqa: E402

load_all_models()

PART_HASH = hashlib.md5(b"first").hexdigest()
UPLOAD_DIR = "/mnt/tmp/beef"
PART_PATH = "/mnt/tmp/beef/1.part"
STAGED_PATH = "/mnt/tmp/beef/.1.deadbeef.part.tmp"
BACKUP_PATH = "/mnt/tmp/beef/.1.deadbeef.part.bak"


class TestMultipartUpload(unittest.IsolatedAsyncioTestCase):
    def _patch(self, target, **kwargs):
        patcher = patch(
            f"app.services.multipart_upload.{target}",
            **kwargs,
        )
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def setUp(self):
        self.log = self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.body = MagicMock()
        self.multipart = ObjektMultipart(
            id=5,
            bucket_id=7,
            user_id=1,
            upload_id="beef",
            object_key="2024/cat.png",
        )

        config = MagicMock()
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        lock_context = AsyncMock()
        lock_context.__aenter__.return_value = None
        lock_context.__aexit__.return_value = None

        self.repo = MagicMock()
        self.repo.rollback = AsyncMock()
        self.repo.commit = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch("uuid.uuid4", return_value=MagicMock(hex="deadbeef"))
        self.bucket_load = self._patch(
            "bucket_load",
            new_callable=AsyncMock,
            return_value=MagicMock(id=7),
        )
        self.multipart_load = self._patch(
            "multipart_load",
            new_callable=AsyncMock,
            return_value=self.multipart,
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
        self.lock = self._patch(
            "locks.lock_file",
            return_value=lock_context,
        )
        self.upload = self._patch("upload", new_callable=AsyncMock)
        self.rename = self._patch("rename", new_callable=AsyncMock)
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.get_file_hash = self._patch(
            "get_file_hash",
            new_callable=AsyncMock,
            return_value=PART_HASH,
        )
        self.get_filesize = self._patch(
            "get_filesize",
            new_callable=AsyncMock,
            return_value=1024,
        )
        self.part_upsert = self._patch(
            "multipart_part_upsert",
            new_callable=AsyncMock,
        )

    async def _upload(self, part_number=1):
        return await multipart_upload(
            session=self.session,
            current_user=self.user,
            bucket_name="photos",
            objekt_key="2024/cat.png",
            upload_id="beef",
            part_number=part_number,
            body=self.body,
        )

    def _paths_for(self, part_number):
        return (
            f"/mnt/tmp/beef/{part_number}.part",
            f"/mnt/tmp/beef/.{part_number}.deadbeef.part.tmp",
            f"/mnt/tmp/beef/.{part_number}.deadbeef.part.bak",
        )

    def _delete_paths(self):
        return [c.args[0] for c in self.delete.await_args_list]

    async def test_first_upload_publishes_and_indexes(self):
        etag = await self._upload()

        self.lock.assert_called_once_with(PART_PATH, LockType.WRITE)
        self.isdir.assert_awaited_once_with(UPLOAD_DIR)
        self.upload.assert_awaited_once_with(self.body, STAGED_PATH)
        self.get_file_hash.assert_awaited_once_with(STAGED_PATH)
        self.get_filesize.assert_awaited_once_with(STAGED_PATH)
        self.isfile.assert_awaited_once_with(PART_PATH)
        self.rename.assert_awaited_once_with(STAGED_PATH, PART_PATH)
        self.part_upsert.assert_awaited_once_with(
            repo=self.repo,
            multipart=self.multipart,
            part_number=1,
            size_bytes=1024,
            etag=PART_HASH,
        )
        self.repo.commit.assert_awaited_once()
        self.delete.assert_not_awaited()
        self.assertEqual(etag, PART_HASH)

    async def test_reupload_backs_up_previous_part_and_cleans_backup(self):
        self.isfile.return_value = True
        part, staged, backup = self._paths_for(2)

        await self._upload(part_number=2)

        self.assertEqual(
            self.rename.await_args_list,
            [
                call(part, backup),
                call(staged, part),
            ],
        )
        self.part_upsert.assert_awaited_once()
        self.repo.commit.assert_awaited_once()
        self.delete.assert_awaited_once_with(backup)

    async def test_reupload_db_failure_restores_previous_part(self):
        self.isfile.return_value = True
        self.part_upsert.side_effect = RuntimeError("db down")
        part, staged, backup = self._paths_for(2)

        with self.assertRaises(RuntimeError):
            await self._upload(part_number=2)

        self.assertEqual(
            self.rename.await_args_list,
            [
                call(part, backup),
                call(staged, part),
                call(backup, part),
            ],
        )
        self.repo.rollback.assert_awaited_once()
        self.repo.commit.assert_not_awaited()
        self.delete.assert_awaited_once_with(staged)

    async def test_commit_failure_removes_published_new_part(self):
        self.repo.commit.side_effect = RuntimeError("commit failed")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.repo.rollback.assert_awaited_once()
        self.assertEqual(
            self._delete_paths(),
            [PART_PATH, STAGED_PATH],
        )

    async def test_publish_failure_restores_backup(self):
        self.isfile.return_value = True
        part, staged, backup = self._paths_for(1)
        self.rename.side_effect = [
            None,
            OSError("busy"),
            None,
        ]

        with self.assertRaises(OSError):
            await self._upload()

        self.assertEqual(
            self.rename.await_args_list,
            [
                call(part, backup),
                call(staged, part),
                call(backup, part),
            ],
        )
        self.part_upsert.assert_not_awaited()
        self.delete.assert_awaited_once_with(staged)

    async def test_failed_temp_upload_does_not_index_or_publish(self):
        self.upload.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.rename.assert_not_awaited()
        self.part_upsert.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_different_part_numbers_use_distinct_locks(self):
        await self._upload(part_number=1)
        await self._upload(part_number=2)

        self.assertEqual(
            [c.args[0] for c in self.lock.call_args_list],
            ["/mnt/tmp/beef/1.part", "/mnt/tmp/beef/2.part"],
        )

    async def test_rejects_part_number_out_of_range(self):
        with self.assertRaises(S3ObjektPartNumberInvalidError):
            await self._upload(part_number=0)

        with self.assertRaises(S3ObjektPartNumberInvalidError):
            await self._upload(part_number=10001)

        self.lock.assert_not_called()
        self.upload.assert_not_awaited()
        self.part_upsert.assert_not_awaited()

    async def test_invalid_key_stops_before_storage(self):
        with self.assertRaises(S3ObjektKeyInvalidError) as cm:
            await multipart_upload(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                objekt_key="../etc/passwd",
                upload_id="beef",
                part_number=1,
                body=self.body,
            )

        self.assertEqual(cm.exception.resource, "/photos/../etc/passwd")
        self.bucket_load.assert_not_awaited()
        self.lock.assert_not_called()
        self.upload.assert_not_awaited()

    async def test_unknown_upload_raises(self):
        self.multipart_load.side_effect = S3ObjektUploadNotFoundError()

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._upload()

        self.upload.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_missing_upload_dir_raises(self):
        self.isdir.return_value = False

        with self.assertRaises(S3ObjektUploadNotFoundError):
            await self._upload()

        self.multipart_load.assert_not_awaited()
        self.upload.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_logs_when_rollback_fails(self):
        self.upload.side_effect = RuntimeError("disk full")
        self.repo.rollback.side_effect = RuntimeError("session closed")

        with self.assertRaises(RuntimeError) as cm:
            await self._upload()

        self.assertEqual(str(cm.exception), "disk full")
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args_list[0].args[0],
        )

    async def test_logs_when_staged_cleanup_fails(self):
        self.upload.side_effect = RuntimeError("disk full")
        self.delete.side_effect = OSError("busy")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "staged_path=%s",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_published_cleanup_fails(self):
        self.repo.commit.side_effect = RuntimeError("commit failed")
        self.delete.side_effect = [OSError("busy"), None]

        with self.assertRaises(RuntimeError):
            await self._upload()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertTrue(
            any("part_path=%s" in message for message in messages),
        )

    async def test_logs_when_restore_fails(self):
        self.isfile.return_value = True
        self.part_upsert.side_effect = RuntimeError("db down")
        self.rename.side_effect = [
            None,
            None,
            OSError("busy"),
        ]

        with self.assertRaises(RuntimeError):
            await self._upload(part_number=2)

        self.assertIn(
            "msg=restore_failed",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_post_commit_backup_cleanup_fails(self):
        self.isfile.return_value = True
        self.delete.side_effect = OSError("busy")

        etag = await self._upload(part_number=2)

        self.assertEqual(etag, PART_HASH)
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "backup_path=%s",
            self.log.exception.call_args.args[0],
        )
