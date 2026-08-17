# tests/services/test_bucket_versioning_put.py
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
    S3IllegalVersioningConfigurationError,
    S3XmlMalformedError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.bucket_versioning_put import bucket_versioning_put  # noqa: E402

load_all_models()


def _versioning_body(status: str) -> bytes:
    return (
        b"<VersioningConfiguration>"
        + f"<Status>{status}</Status>".encode()
        + b"</VersioningConfiguration>"
    )


class TestBucketVersioningPut(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.log_patcher = patch("app.services.bucket_versioning_put.log")
        self.log = self.log_patcher.start()
        self.session = MagicMock()
        self.user = User(id=1, username="alice", is_root=False)

    def tearDown(self):
        self.log_patcher.stop()

    def _bucket(
        self,
        versioning_status: str,
        *,
        object_lock_enabled: bool = False,
    ) -> Bucket:
        return Bucket(
            id=7,
            user_id=1,
            bucket_name="photos",
            versioning_status=versioning_status,
            object_lock_enabled=object_lock_enabled,
        )

    def _repo(self):
        repo = MagicMock()
        repo.update = AsyncMock()
        repo.commit = AsyncMock()
        repo.rollback = AsyncMock()
        return repo

    async def _put(self, bucket, body, repo=None, user=None):
        repo = repo if repo is not None else self._repo()

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ) as load_bucket_mock,
        ):
            await bucket_versioning_put(
                session=self.session,
                current_user=user or self.user,
                bucket_name="photos",
                body=body,
            )

        return repo, load_bucket_mock

    async def test_enables_from_disabled(self):
        bucket = self._bucket(BUCKET_VERSIONING_DISABLED)

        repo, load_bucket_mock = await self._put(
            bucket,
            _versioning_body(BUCKET_VERSIONING_ENABLED),
        )

        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)
        load_bucket_mock.assert_awaited_once_with(
            repo,
            "photos",
            self.user,
            "/photos",
        )
        repo.update.assert_awaited_once_with(bucket)
        repo.commit.assert_awaited_once()
        repo.rollback.assert_not_awaited()

    async def test_suspends_from_disabled(self):
        bucket = self._bucket(BUCKET_VERSIONING_DISABLED)

        await self._put(
            bucket,
            _versioning_body(BUCKET_VERSIONING_SUSPENDED),
        )

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_SUSPENDED,
        )

    async def test_suspends_from_enabled(self):
        bucket = self._bucket(BUCKET_VERSIONING_ENABLED)

        await self._put(
            bucket,
            _versioning_body(BUCKET_VERSIONING_SUSPENDED),
        )

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_SUSPENDED,
        )

    async def test_reenables_from_suspended(self):
        bucket = self._bucket(BUCKET_VERSIONING_SUSPENDED)

        await self._put(
            bucket,
            _versioning_body(BUCKET_VERSIONING_ENABLED),
        )

        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)

    async def test_rejects_malformed_xml(self):
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
            ) as load_bucket_mock,
        ):
            with self.assertRaises(S3XmlMalformedError) as cm:
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=b"<VersioningConfiguration>",
                )

        self.assertEqual(cm.exception.resource, "/photos")
        load_bucket_mock.assert_not_awaited()
        repo.update.assert_not_awaited()

    async def test_rejects_disabled_status(self):
        bucket = self._bucket(BUCKET_VERSIONING_ENABLED)
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(S3IllegalVersioningConfigurationError) as cm:
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=_versioning_body(BUCKET_VERSIONING_DISABLED),
                )

        self.assertEqual(cm.exception.resource, "/photos")
        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)
        repo.update.assert_not_awaited()
        repo.commit.assert_not_awaited()

    async def test_rejects_unknown_status(self):
        bucket = self._bucket(BUCKET_VERSIONING_ENABLED)
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(S3IllegalVersioningConfigurationError) as cm:
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=_versioning_body("Invalid"),
                )

        self.assertEqual(cm.exception.resource, "/photos")
        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)
        repo.update.assert_not_awaited()

    async def test_rejects_suspend_when_object_lock_enabled(self):
        bucket = self._bucket(
            BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
        )
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(S3BucketStateInvalidError) as cm:
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=_versioning_body(BUCKET_VERSIONING_SUSPENDED),
                )

        self.assertEqual(cm.exception.resource, "/photos")
        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)
        repo.update.assert_not_awaited()

    async def test_bucket_not_found_raises(self):
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3BucketNotFoundError("/photos"),
            ),
        ):
            with self.assertRaises(S3BucketNotFoundError):
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=_versioning_body(BUCKET_VERSIONING_ENABLED),
                )

        repo.update.assert_not_awaited()
        repo.commit.assert_not_awaited()

    async def test_access_denied_raises(self):
        other_user = User(id=99, username="eve", is_root=False)
        repo = self._repo()

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                side_effect=S3AccessDeniedError("/photos"),
            ),
        ):
            with self.assertRaises(S3AccessDeniedError):
                await bucket_versioning_put(
                    session=self.session,
                    current_user=other_user,
                    bucket_name="photos",
                    body=_versioning_body(BUCKET_VERSIONING_ENABLED),
                )

        repo.update.assert_not_awaited()

    async def test_rolls_back_when_update_fails(self):
        bucket = self._bucket(BUCKET_VERSIONING_DISABLED)
        repo = self._repo()
        repo.update = AsyncMock(side_effect=RuntimeError("db down"))

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(RuntimeError):
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=_versioning_body(BUCKET_VERSIONING_ENABLED),
                )

        repo.rollback.assert_awaited_once()
        repo.commit.assert_not_awaited()

    async def test_rolls_back_when_commit_fails(self):
        bucket = self._bucket(BUCKET_VERSIONING_DISABLED)
        repo = self._repo()
        repo.commit = AsyncMock(side_effect=RuntimeError("db down"))

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(RuntimeError):
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=_versioning_body(BUCKET_VERSIONING_ENABLED),
                )

        repo.update.assert_awaited_once_with(bucket)
        repo.rollback.assert_awaited_once()

    async def test_logs_when_rollback_fails(self):
        bucket = self._bucket(BUCKET_VERSIONING_DISABLED)
        repo = self._repo()
        repo.update = AsyncMock(side_effect=RuntimeError("db down"))
        repo.rollback = AsyncMock(side_effect=RuntimeError("session closed"))

        with (
            patch(
                "app.services.bucket_versioning_put.ORMRepository",
                return_value=repo,
            ),
            patch(
                "app.services.bucket_versioning_put.load_bucket",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
        ):
            with self.assertRaises(RuntimeError) as cm:
                await bucket_versioning_put(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                    body=_versioning_body(BUCKET_VERSIONING_ENABLED),
                )

        self.assertEqual(str(cm.exception), "db down")
        repo.rollback.assert_awaited_once()
        self.log.exception.assert_called_once()
        self.assertIn(
            "msg=rollback_failed",
            self.log.exception.call_args.args[0],
        )
