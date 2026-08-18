# tests/services/test_objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import OBJECT_CONTENT_TYPE_DEFAULT  # noqa: E402
from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3BucketNotFoundError,
    S3ObjectKeyConflictError,
    S3ObjectKeyInvalidError,
)
from app.hooks import Events  # noqa: E402
from app.locks import LockType  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.objekt_upload import objekt_upload  # noqa: E402

load_all_models()

BUCKET_PATH = "/mnt/buckets/photos"
OBJEKT_PATH = "/mnt/buckets/photos/2024/cat.png"
STAGED_PATH = "/mnt/tmp/staged"
BACKUP_PATH = "/mnt/tmp/backup"
RESOURCE = "/photos/2024/cat.png"


class TestObjektUpload(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log = self._patch("log")
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()
        self.body = MagicMock()
        self.bucket = Bucket(id=7, user_id=1, bucket_name="photos")
        self.objekt = Objekt(
            id=3,
            bucket_id=7,
            user_id=1,
            object_key="2024/cat.png",
            size_bytes=12,
            etag="etag123",
            content_type="image/png",
        )

    def _patch(self, target, **kwargs):
        patcher = patch(f"app.services.objekt_upload.{target}", **kwargs)
        mock = patcher.start()
        self.addCleanup(patcher.stop)
        return mock

    def _build_lock_context(self):
        ctx = AsyncMock()
        ctx.__aenter__.return_value = None
        ctx.__aexit__.return_value = None
        return ctx

    def _build_mocks(self, *, mimetype="image/png", object_exists=False):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        config.MOUNTPOINT_TMP_DIR = "/mnt/tmp"

        self.repo = MagicMock()
        self.repo.commit = AsyncMock()
        self.repo.rollback = AsyncMock()

        self._patch("get_config", return_value=config)
        self._patch("ORMRepository", return_value=self.repo)
        self._patch(
            "uuid.uuid4",
            side_effect=[
                MagicMock(hex="staged"),
                MagicMock(hex="backup"),
            ],
        )
        self.lock = self._patch(
            "locks.lock_directory",
            return_value=self._build_lock_context(),
        )
        self.load_bucket = self._patch(
            "load_bucket",
            new_callable=AsyncMock,
            return_value=self.bucket,
        )
        self.isdir = self._patch(
            "isdir",
            new_callable=AsyncMock,
            return_value=True,
        )
        self.isfile = self._patch(
            "isfile",
            new_callable=AsyncMock,
            return_value=object_exists,
        )
        self.objekt_mkdir = self._patch(
            "objekt_mkdir",
            new_callable=AsyncMock,
        )
        self.upsert_objekt = self._patch(
            "upsert_objekt",
            new_callable=AsyncMock,
            return_value=self.objekt,
        )
        self.upload = self._patch("upload", new_callable=AsyncMock)
        self.copy = self._patch("copy", new_callable=AsyncMock)
        self._patch(
            "get_filesize",
            new_callable=AsyncMock,
            return_value=12,
        )
        self._patch(
            "get_file_hash",
            new_callable=AsyncMock,
            return_value="etag123",
        )
        self._patch(
            "get_mimetype",
            new_callable=AsyncMock,
            return_value=mimetype,
        )
        self.rename = self._patch("rename", new_callable=AsyncMock)
        self.delete = self._patch("delete", new_callable=AsyncMock)
        self.emit = self._patch("hooks.emit", new_callable=AsyncMock)

    async def _upload(self, key="2024/cat.png"):
        return await objekt_upload(
            session=self.session,
            current_user=self.user,
            bucket_name="photos",
            objekt_key=key,
            body=self.body,
        )

    def _delete_paths(self):
        return [c.args[0] for c in self.delete.await_args_list]

    async def test_stages_and_publishes_new_object(self):
        self._build_mocks()

        objekt = await self._upload()

        self.lock.assert_called_once_with(BUCKET_PATH, LockType.WRITE)
        self.isdir.assert_awaited_once_with(BUCKET_PATH)
        self.upload.assert_awaited_once_with(self.body, STAGED_PATH)
        self.objekt_mkdir.assert_awaited_once_with(OBJEKT_PATH, RESOURCE)
        self.isfile.assert_awaited_once_with(OBJEKT_PATH)
        self.copy.assert_not_awaited()
        self.rename.assert_awaited_once_with(STAGED_PATH, OBJEKT_PATH)
        self.repo.commit.assert_awaited_once()
        self.delete.assert_not_awaited()
        self.assertIs(objekt, self.objekt)
        self.emit.assert_awaited_once_with(Events.OBJECT_UPLOADED, objekt)

    async def test_overwrites_existing_object_and_cleans_backup(self):
        self._build_mocks(object_exists=True)

        await self._upload()

        self.copy.assert_awaited_once_with(OBJEKT_PATH, BACKUP_PATH)
        self.rename.assert_awaited_once_with(STAGED_PATH, OBJEKT_PATH)
        self.repo.commit.assert_awaited_once()
        self.delete.assert_awaited_once_with(BACKUP_PATH)

    async def test_upserts_metadata_of_staged_body(self):
        self._build_mocks()

        await self._upload()

        kwargs = self.upsert_objekt.await_args.kwargs
        self.assertIs(kwargs["bucket"], self.bucket)
        self.assertIs(kwargs["user"], self.user)
        self.assertEqual(kwargs["object_key"], "2024/cat.png")
        self.assertEqual(kwargs["size_bytes"], 12)
        self.assertEqual(kwargs["etag"], "etag123")
        self.assertEqual(kwargs["content_type"], "image/png")

    async def test_unknown_mimetype_falls_back_to_octet_stream(self):
        self._build_mocks(mimetype=None)

        await self._upload()

        self.assertEqual(
            self.upsert_objekt.await_args.kwargs["content_type"],
            OBJECT_CONTENT_TYPE_DEFAULT,
        )

    async def test_rejects_key_escaping_the_bucket(self):
        self._build_mocks()

        with self.assertRaises(S3ObjectKeyInvalidError) as cm:
            await self._upload(key="../../etc/passwd")

        self.assertEqual(
            cm.exception.resource,
            "/photos/../../etc/passwd",
        )
        self.load_bucket.assert_not_awaited()
        self.lock.assert_not_called()
        self.upload.assert_not_awaited()

    async def test_inaccessible_bucket_stops_before_lock(self):
        self._build_mocks()
        self.load_bucket.side_effect = S3BucketNotFoundError("/photos")

        with self.assertRaises(S3BucketNotFoundError):
            await self._upload()

        self.lock.assert_not_called()
        self.upload.assert_not_awaited()
        self.delete.assert_not_awaited()
        self.emit.assert_not_awaited()

    async def test_missing_bucket_dir_cleans_staged_path(self):
        self._build_mocks()
        self.isdir.return_value = False

        with self.assertRaises(S3BucketNotFoundError):
            await self._upload()

        self.upload.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with(STAGED_PATH)
        self.emit.assert_not_awaited()

    async def test_failed_upload_cleans_staged_path(self):
        self._build_mocks()
        self.upload.side_effect = RuntimeError("disk full")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with(STAGED_PATH)
        self.emit.assert_not_awaited()

    async def test_key_conflict_on_mkdir_cleans_staged_path(self):
        self._build_mocks()
        self.objekt_mkdir.side_effect = S3ObjectKeyConflictError(RESOURCE)

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._upload()

        self.rename.assert_not_awaited()
        self.copy.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_directory_at_object_path_is_a_key_conflict(self):
        self._build_mocks()
        self.rename.side_effect = IsADirectoryError()

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._upload()

        self.repo.commit.assert_not_awaited()
        self.repo.rollback.assert_awaited_once()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_object_at_key_prefix_is_a_key_conflict(self):
        self._build_mocks()
        self.rename.side_effect = NotADirectoryError()

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._upload()

        self.repo.commit.assert_not_awaited()
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_rename_conflict_discards_backup_when_object_existed(self):
        self._build_mocks(object_exists=True)
        self.rename.side_effect = IsADirectoryError()

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._upload()

        self.copy.assert_awaited_once_with(OBJEKT_PATH, BACKUP_PATH)
        self.assertEqual(
            self._delete_paths(),
            [BACKUP_PATH, STAGED_PATH],
        )

    async def test_upsert_failure_discards_backup_when_object_existed(self):
        self._build_mocks(object_exists=True)
        self.upsert_objekt.side_effect = RuntimeError("db down")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.rename.assert_not_awaited()
        self.assertEqual(
            self._delete_paths(),
            [BACKUP_PATH, STAGED_PATH],
        )

    async def test_commit_failure_deletes_published_new_object(self):
        self._build_mocks()
        self.repo.commit.side_effect = RuntimeError("commit failed")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.repo.rollback.assert_awaited_once()
        self.assertEqual(
            self._delete_paths(),
            [OBJEKT_PATH, STAGED_PATH],
        )
        self.copy.assert_not_awaited()
        self.emit.assert_not_awaited()

    async def test_commit_failure_restores_overwritten_object(self):
        self._build_mocks(object_exists=True)
        self.repo.commit.side_effect = RuntimeError("commit failed")

        with self.assertRaises(RuntimeError):
            await self._upload()

        self.assertEqual(
            self.copy.await_args_list,
            [
                call(OBJEKT_PATH, BACKUP_PATH),
                call(BACKUP_PATH, OBJEKT_PATH),
            ],
        )
        self.assertEqual(
            self._delete_paths(),
            [BACKUP_PATH, STAGED_PATH],
        )
        self.emit.assert_not_awaited()

    async def test_logs_when_rollback_fails(self):
        self._build_mocks()
        self.upload.side_effect = RuntimeError("disk full")
        self.repo.rollback.side_effect = RuntimeError("session closed")

        with self.assertRaises(RuntimeError) as cm:
            await self._upload()

        self.assertEqual(str(cm.exception), "disk full")
        self.log.exception.assert_called()
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args_list[0].args[0],
        )
        self.delete.assert_awaited_once_with(STAGED_PATH)

    async def test_logs_when_staged_cleanup_fails(self):
        self._build_mocks()
        self.upload.side_effect = RuntimeError("disk full")
        self.delete.side_effect = OSError("busy")

        with self.assertRaises(RuntimeError) as cm:
            await self._upload()

        self.assertEqual(str(cm.exception), "disk full")
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "staged_path=%s",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_published_cleanup_fails(self):
        self._build_mocks()
        self.repo.commit.side_effect = RuntimeError("commit failed")
        self.delete.side_effect = [OSError("busy"), None]

        with self.assertRaises(RuntimeError):
            await self._upload()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertTrue(
            any("objekt_path=%s" in message for message in messages),
        )

    async def test_logs_when_restore_fails(self):
        self._build_mocks(object_exists=True)
        self.repo.commit.side_effect = RuntimeError("commit failed")
        self.copy.side_effect = [None, OSError("busy")]

        with self.assertRaises(RuntimeError):
            await self._upload()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertTrue(
            any("msg=restore_failed" in message for message in messages),
        )
        # Restore failed, so the backup must not be deleted as "success".
        self.assertEqual(self._delete_paths(), [STAGED_PATH])

    async def test_logs_when_backup_cleanup_after_restore_fails(self):
        self._build_mocks(object_exists=True)
        self.repo.commit.side_effect = RuntimeError("commit failed")

        def delete_side_effect(path):
            if path == BACKUP_PATH:
                raise OSError("busy")
            return None

        self.delete.side_effect = delete_side_effect

        with self.assertRaises(RuntimeError):
            await self._upload()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertTrue(
            any("backup_path=%s" in message for message in messages),
        )

    async def test_logs_when_backup_discard_before_publish_fails(self):
        self._build_mocks(object_exists=True)
        self.rename.side_effect = IsADirectoryError()

        def delete_side_effect(path):
            if path == BACKUP_PATH:
                raise OSError("busy")
            return None

        self.delete.side_effect = delete_side_effect

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._upload()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertTrue(
            any("backup_path=%s" in message for message in messages),
        )

    async def test_logs_when_post_commit_backup_cleanup_fails(self):
        self._build_mocks(object_exists=True)
        self.delete.side_effect = OSError("busy")

        objekt = await self._upload()

        self.assertIs(objekt, self.objekt)
        self.emit.assert_awaited_once_with(
            Events.OBJECT_UPLOADED,
            objekt,
        )
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )
        self.assertIn(
            "backup_path=%s",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_rollback_and_cleanup_failures(self):
        self._build_mocks()
        self.rename.side_effect = IsADirectoryError()
        self.repo.rollback.side_effect = RuntimeError("session closed")
        self.delete.side_effect = OSError("busy")

        with self.assertRaises(S3ObjectKeyConflictError):
            await self._upload()

        messages = [
            c.args[0] for c in self.log.exception.call_args_list
        ]
        self.assertEqual(len(messages), 2)
        self.assertIn("msg=rollback_failed", messages[0])
        self.assertIn("msg=cleanup_failed", messages[1])
