# tests/services/test_bucket_create.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.exc import IntegrityError

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3BucketAlreadyExistsError,
    S3BucketAlreadyOwnedByYouError,
    S3InvalidBucketNameError,
)
from app.hooks import Events  # noqa: E402
from app.locks import LockType  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.bucket_create import bucket_create  # noqa: E402

load_all_models()


class TestBucketCreate(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.bucket_create.log")
        self.log = self.log_patcher.start()
        self.user = User(id=1, username="alice", is_root=False)
        self.session = MagicMock()

    def tearDown(self):
        self.log_patcher.stop()

    def _build_lock_context(self):
        ctx = AsyncMock()
        ctx.__aenter__.return_value = None
        ctx.__aexit__.return_value = None
        return ctx

    async def test_creates_dir_and_bucket_row(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)
        repo.insert = AsyncMock(side_effect=lambda obj, **kwargs: obj)
        repo.commit = AsyncMock()

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ) as lock_mock,
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
            ) as mkdir_mock,
            patch(
                "app.services.bucket_create.hooks.emit",
                new_callable=AsyncMock,
            ) as emit_mock,
        ):
            bucket = await bucket_create(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
            )

        lock_mock.assert_called_once_with(
            "/mnt/buckets/photos",
            LockType.WRITE,
        )
        mkdir_mock.assert_awaited_once_with("/mnt/buckets/photos")
        repo.insert.assert_awaited_once()
        inserted = repo.insert.await_args.args[0]
        self.assertIsInstance(inserted, Bucket)
        self.assertEqual(inserted.bucket_name, "photos")
        self.assertEqual(inserted.user_id, 1)
        repo.commit.assert_awaited_once()
        emit_mock.assert_awaited_once_with(Events.BUCKET_CREATED, bucket)

    async def test_already_owned_raises(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        existing = Bucket(user_id=1, bucket_name="photos")
        repo = MagicMock()
        repo.select = AsyncMock(return_value=existing)

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
        ):
            with self.assertRaises(S3BucketAlreadyOwnedByYouError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

    async def test_already_exists_for_other_user(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        existing = Bucket(user_id=99, bucket_name="photos")
        repo = MagicMock()
        repo.select = AsyncMock(return_value=existing)

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
        ):
            with self.assertRaises(S3BucketAlreadyExistsError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

    async def test_orphan_dir_raises(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            with self.assertRaises(S3BucketAlreadyExistsError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        repo.insert.assert_not_called()

    async def test_file_at_bucket_path_raises(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            with self.assertRaises(S3BucketAlreadyExistsError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        repo.insert.assert_not_called()

    async def test_rolls_back_when_insert_fails(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)
        repo.insert = AsyncMock(side_effect=IntegrityError("", "", Exception()))
        repo.rollback = AsyncMock()

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
            ) as mktree_mock,
            patch(
                "app.services.bucket_create.rmdir",
                new_callable=AsyncMock,
            ) as rmdir_mock,
        ):
            with self.assertRaises(IntegrityError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        repo.rollback.assert_awaited_once()
        mktree_mock.assert_not_awaited()
        rmdir_mock.assert_not_awaited()

    async def test_rolls_back_when_mktree_fails(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)
        repo.insert = AsyncMock(side_effect=lambda obj, **kwargs: obj)
        repo.rollback = AsyncMock()

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
                side_effect=OSError("disk full"),
            ),
            patch(
                "app.services.bucket_create.rmdir",
                new_callable=AsyncMock,
            ) as rmdir_mock,
        ):
            with self.assertRaises(OSError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        repo.rollback.assert_awaited_once()
        rmdir_mock.assert_not_awaited()

    async def test_rolls_back_dir_when_commit_fails(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)
        repo.insert = AsyncMock(side_effect=lambda obj, **kwargs: obj)
        repo.commit = AsyncMock(side_effect=RuntimeError("db down"))
        repo.rollback = AsyncMock()
        isdir_mock = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new=isdir_mock,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.bucket_create.rmdir",
                new_callable=AsyncMock,
            ) as rmdir_mock,
        ):
            with self.assertRaises(RuntimeError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        repo.rollback.assert_awaited_once()
        rmdir_mock.assert_awaited_once_with("/mnt/buckets/photos")

    async def test_logs_when_cleanup_fails(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)
        repo.insert = AsyncMock(side_effect=lambda obj, **kwargs: obj)
        repo.commit = AsyncMock(side_effect=RuntimeError("db down"))
        repo.rollback = AsyncMock()

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.bucket_create.rmdir",
                new_callable=AsyncMock,
                side_effect=OSError("busy"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        self.log.exception.assert_called_once()
        self.assertIn(
            "msg=cleanup_failed",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_when_rollback_fails(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)
        repo.insert = AsyncMock(side_effect=IntegrityError("", "", Exception()))
        repo.rollback = AsyncMock(side_effect=RuntimeError("session closed"))

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
            ) as mktree_mock,
            patch(
                "app.services.bucket_create.rmdir",
                new_callable=AsyncMock,
            ) as rmdir_mock,
        ):
            with self.assertRaises(IntegrityError):
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        repo.rollback.assert_awaited_once()
        mktree_mock.assert_not_awaited()
        rmdir_mock.assert_not_awaited()
        self.log.exception.assert_called_once()
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args.args[0],
        )

    async def test_logs_rollback_and_cleans_dir_when_both_fail_after_mktree(self):
        config = MagicMock()
        config.MOUNTPOINT_BUCKETS_DIR = "/mnt/buckets"
        lock_ctx = self._build_lock_context()
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)
        repo.insert = AsyncMock(side_effect=lambda obj, **kwargs: obj)
        repo.commit = AsyncMock(side_effect=RuntimeError("db down"))
        repo.rollback = AsyncMock(side_effect=RuntimeError("session closed"))

        with (
            patch(
                "app.services.bucket_create.get_config",
                return_value=config,
            ),
            patch(
                "app.services.bucket_create.locks.lock_directory",
                return_value=lock_ctx,
            ),
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.isdir",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.isfile",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.bucket_create.rmdir",
                new_callable=AsyncMock,
            ) as rmdir_mock,
        ):
            with self.assertRaises(RuntimeError) as cm:
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

        self.assertEqual(str(cm.exception), "db down")
        rmdir_mock.assert_awaited_once_with("/mnt/buckets/photos")
        self.log.exception.assert_called_once()
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args.args[0],
        )

    async def test_invalid_bucket_name_stops_before_storage(self):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=None)

        with (
            patch(
                "app.services.bucket_create.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_create.mktree",
                new_callable=AsyncMock,
            ) as mktree_mock,
        ):
            with self.assertRaises(S3InvalidBucketNameError) as cm:
                await bucket_create(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="Bad_Name",
                )

        self.assertEqual(cm.exception.resource, "/Bad_Name")
        repo.select.assert_not_awaited()
        mktree_mock.assert_not_awaited()
