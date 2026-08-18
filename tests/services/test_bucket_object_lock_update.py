# tests/services/test_bucket_object_lock_update.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import (  # noqa: E402
    BUCKET_VERSIONING_DISABLED,
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
)
from app.db.engine import load_all_models  # noqa: E402
from app.errors import (  # noqa: E402
    S3AccessDeniedError,
    S3BucketNotFoundError,
    S3BucketStateInvalidError,
    S3XmlMalformedError,
)
from app.hooks import Events  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.bucket_object_lock_update import (  # noqa: E402
    bucket_object_lock_update,
)

load_all_models()


ENABLED_BODY = (
    b"<ObjectLockConfiguration>"
    b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
    b"</ObjectLockConfiguration>"
)

GOVERNANCE_DAYS_BODY = (
    b"<ObjectLockConfiguration>"
    b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
    b"<Rule><DefaultRetention>"
    b"<Mode>GOVERNANCE</Mode>"
    b"<Days>10</Days>"
    b"</DefaultRetention></Rule>"
    b"</ObjectLockConfiguration>"
)

COMPLIANCE_YEARS_BODY = (
    b"<ObjectLockConfiguration>"
    b"<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
    b"<Rule><DefaultRetention>"
    b"<Mode>COMPLIANCE</Mode>"
    b"<Years>2</Years>"
    b"</DefaultRetention></Rule>"
    b"</ObjectLockConfiguration>"
)

EMPTY_BODY = b"<ObjectLockConfiguration></ObjectLockConfiguration>"


class TestBucketObjectLockUpdate(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.bucket_object_lock_update.log")
        self.log = self.log_patcher.start()
        self.session = MagicMock()
        self.user = User(id=1, username="alice", is_root=False)

    def tearDown(self):
        self.log_patcher.stop()

    def _bucket(self, **kwargs) -> Bucket:
        values = {
            "id": 7,
            "user_id": 1,
            "bucket_name": "photos",
            "versioning_status": BUCKET_VERSIONING_ENABLED,
            "object_lock_enabled": False,
        }
        values.update(kwargs)
        return Bucket(**values)

    def _repo(self):
        repo = MagicMock()
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.rollback = AsyncMock()
        return repo

    async def _update(self, bucket, body, repo=None, user=None):
        repo = repo if repo is not None else self._repo()
        emit = AsyncMock()

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ) as load_bucket_mock,
            patch(
                "app.services.bucket_object_lock_update.hooks.emit",
                new=emit,
            ),
        ):
            await bucket_object_lock_update(
                session=self.session,
                current_user=user or self.user,
                bucket_name="photos",
                body=body,
            )

        return repo, load_bucket_mock, emit

    async def test_enables_object_lock(self):
        bucket = self._bucket()

        repo, load_bucket_mock, emit = await self._update(
            bucket,
            ENABLED_BODY,
        )

        self.assertTrue(bucket.object_lock_enabled)
        self.assertIsNone(bucket.default_lock_mode)
        load_bucket_mock.assert_awaited_once_with(
            repo,
            "photos",
            self.user,
            "/photos",
        )
        repo.update.assert_awaited_once_with(bucket)
        repo.commit.assert_awaited_once()
        repo.rollback.assert_not_awaited()
        emit.assert_awaited_once_with(
            Events.BUCKET_OBJECT_LOCK_UPDATED,
            bucket,
        )

    async def test_sets_governance_days(self):
        bucket = self._bucket()

        await self._update(bucket, GOVERNANCE_DAYS_BODY)

        self.assertTrue(bucket.object_lock_enabled)
        self.assertEqual(bucket.default_lock_mode, "GOVERNANCE")
        self.assertEqual(bucket.default_retention_days, 10)
        self.assertIsNone(bucket.default_retention_years)

    async def test_sets_compliance_years(self):
        bucket = self._bucket()

        await self._update(bucket, COMPLIANCE_YEARS_BODY)

        self.assertTrue(bucket.object_lock_enabled)
        self.assertEqual(bucket.default_lock_mode, "COMPLIANCE")
        self.assertIsNone(bucket.default_retention_days)
        self.assertEqual(bucket.default_retention_years, 2)

    async def test_clears_default_rule_without_disabling_lock(self):
        bucket = self._bucket(
            object_lock_enabled=True,
            default_lock_mode="GOVERNANCE",
            default_retention_days=10,
        )

        await self._update(bucket, EMPTY_BODY)

        self.assertTrue(bucket.object_lock_enabled)
        self.assertIsNone(bucket.default_lock_mode)
        self.assertIsNone(bucket.default_retention_days)
        self.assertIsNone(bucket.default_retention_years)

    async def test_rejects_malformed_xml(self):
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
            ) as load_bucket_mock,
            patch(
                "app.services.bucket_object_lock_update.hooks.emit",
                new_callable=AsyncMock,
            ) as emit,
        ):
            with self.assertRaises(S3XmlMalformedError) as cm:
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=b"<ObjectLockConfiguration>",
                )

        self.assertEqual(cm.exception.resource, "/photos")
        load_bucket_mock.assert_not_awaited()
        repo.update.assert_not_awaited()
        emit.assert_not_awaited()

    async def test_rejects_when_versioning_disabled(self):
        bucket = self._bucket(versioning_status=BUCKET_VERSIONING_DISABLED)
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
            patch(
                "app.services.bucket_object_lock_update.hooks.emit",
                new_callable=AsyncMock,
            ) as emit,
        ):
            with self.assertRaises(S3BucketStateInvalidError) as cm:
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=ENABLED_BODY,
                )

        self.assertEqual(cm.exception.resource, "/photos")
        self.assertFalse(bucket.object_lock_enabled)
        repo.update.assert_not_awaited()
        emit.assert_not_awaited()

    async def test_rejects_when_versioning_suspended(self):
        bucket = self._bucket(versioning_status=BUCKET_VERSIONING_SUSPENDED)
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(S3BucketStateInvalidError):
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=ENABLED_BODY,
                )

        repo.update.assert_not_awaited()

    async def test_bucket_not_found_raises(self):
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3BucketNotFoundError("/photos"),
            ),
        ):
            with self.assertRaises(S3BucketNotFoundError):
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=ENABLED_BODY,
                )

        repo.update.assert_not_awaited()

    async def test_access_denied_raises(self):
        other_user = User(id=99, username="eve", is_root=False)
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3AccessDeniedError("/photos"),
            ),
        ):
            with self.assertRaises(S3AccessDeniedError):
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=other_user,
                    bucket_name="photos",
                    body=ENABLED_BODY,
                )

        repo.update.assert_not_awaited()

    async def test_rolls_back_when_update_fails(self):
        bucket = self._bucket()
        repo = self._repo()
        repo.update = AsyncMock(side_effect=RuntimeError("db down"))

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
            patch(
                "app.services.bucket_object_lock_update.hooks.emit",
                new_callable=AsyncMock,
            ) as emit,
        ):
            with self.assertRaises(RuntimeError):
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=ENABLED_BODY,
                )

        repo.rollback.assert_awaited_once()
        repo.commit.assert_not_awaited()
        emit.assert_not_awaited()

    async def test_rolls_back_when_commit_fails(self):
        bucket = self._bucket()
        repo = self._repo()
        repo.commit = AsyncMock(side_effect=RuntimeError("db down"))

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
            patch(
                "app.services.bucket_object_lock_update.hooks.emit",
                new_callable=AsyncMock,
            ) as emit,
        ):
            with self.assertRaises(RuntimeError):
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=ENABLED_BODY,
                )

        repo.update.assert_awaited_once_with(bucket)
        repo.rollback.assert_awaited_once()
        emit.assert_not_awaited()

    async def test_logs_when_rollback_fails(self):
        bucket = self._bucket()
        repo = self._repo()
        repo.update = AsyncMock(side_effect=RuntimeError("db down"))
        repo.rollback = AsyncMock(side_effect=RuntimeError("session closed"))

        with (
            patch(
                "app.services.bucket_object_lock_update.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_object_lock_update.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(RuntimeError) as cm:
                await bucket_object_lock_update(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=ENABLED_BODY,
                )

        self.assertEqual(str(cm.exception), "db down")
        repo.rollback.assert_awaited_once()
        self.log.exception.assert_called_once()
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args.args[0],
        )
