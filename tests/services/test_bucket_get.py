# tests/services/test_bucket_get.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3BucketNotFoundError, S3AccessDeniedError  # noqa: E402
from app.hooks import Events  # noqa: E402
from app.models.bucket import S3Bucket  # noqa: E402
from app.models.object import S3Object  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.bucket_get import bucket_get  # noqa: E402

load_all_models()


class TestBucketGet(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = MagicMock()
        self.user = User(id=1, username="alice", is_root=False)
        self.bucket = S3Bucket(id=7, user_id=1, bucket_name="photos")

    def _build_repo(self, bucket=None, s3_objects=None):
        repo = MagicMock()
        repo.select = AsyncMock(return_value=bucket if bucket is not None else self.bucket)
        repo.select_all = AsyncMock(return_value=s3_objects or [])
        return repo

    async def test_lists_all_objects_without_prefix(self):
        s3_object = S3Object(
            id=1, bucket_id=7, user_id=1,
            object_key="photo.jpg", size_bytes=100,
            etag="abc", content_type="image/jpeg",
        )
        repo = self._build_repo(s3_objects=[s3_object])

        with (
            patch("app.services.bucket_get.ORMRepository", return_value=repo),
            patch(
                "app.services.bucket_get.load_bucket",
                new=AsyncMock(return_value=self.bucket),
            ),
            patch(
                "app.services.bucket_get.hooks.emit",
                new_callable=AsyncMock,
            ) as emit_mock,
        ):
            result = await bucket_get(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
            )

        repo.select_all.assert_awaited_once_with(
            S3Object,
            bucket_id=7,
            delete_marker=False,
            order_by="object_key",
            order="asc",
            limit=1000,
        )
        self.assertEqual(result, [s3_object])
        emit_mock.assert_awaited_once_with(Events.OBJECT_LISTED, [s3_object])

    async def test_lists_objects_with_prefix(self):
        s3_object = S3Object(
            id=2, bucket_id=7, user_id=1,
            object_key="2024/cat.png", size_bytes=50,
            etag="def", content_type="image/png",
        )
        repo = self._build_repo(s3_objects=[s3_object])

        with (
            patch("app.services.bucket_get.ORMRepository", return_value=repo),
            patch(
                "app.services.bucket_get.load_bucket",
                new=AsyncMock(return_value=self.bucket),
            ),
            patch(
                "app.services.bucket_get.hooks.emit",
                new_callable=AsyncMock,
            ),
        ):
            result = await bucket_get(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                prefix="2024/",
            )

        repo.select_all.assert_awaited_once_with(
            S3Object,
            bucket_id=7,
            delete_marker=False,
            order_by="object_key",
            order="asc",
            limit=1000,
            object_key__like="2024/%",
        )
        self.assertEqual(result, [s3_object])

    async def test_prefix_special_chars_are_escaped(self):
        repo = self._build_repo(s3_objects=[])

        with (
            patch("app.services.bucket_get.ORMRepository", return_value=repo),
            patch(
                "app.services.bucket_get.load_bucket",
                new=AsyncMock(return_value=self.bucket),
            ),
            patch("app.services.bucket_get.hooks.emit", new_callable=AsyncMock),
        ):
            await bucket_get(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                prefix="a%b_c",
            )

        call_kwargs = repo.select_all.call_args.kwargs
        self.assertEqual(call_kwargs["object_key__like"], r"a\%b\_c%")

    async def test_respects_max_keys(self):
        repo = self._build_repo(s3_objects=[])

        with (
            patch("app.services.bucket_get.ORMRepository", return_value=repo),
            patch(
                "app.services.bucket_get.load_bucket",
                new=AsyncMock(return_value=self.bucket),
            ),
            patch("app.services.bucket_get.hooks.emit", new_callable=AsyncMock),
        ):
            await bucket_get(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
                max_keys=10,
            )

        call_kwargs = repo.select_all.call_args.kwargs
        self.assertEqual(call_kwargs["limit"], 10)

    async def test_returns_empty_list(self):
        repo = self._build_repo(s3_objects=[])

        with (
            patch("app.services.bucket_get.ORMRepository", return_value=repo),
            patch(
                "app.services.bucket_get.load_bucket",
                new=AsyncMock(return_value=self.bucket),
            ),
            patch(
                "app.services.bucket_get.hooks.emit",
                new_callable=AsyncMock,
            ) as emit_mock,
        ):
            result = await bucket_get(
                session=self.session,
                current_user=self.user,
                bucket_name="photos",
            )

        self.assertEqual(result, [])
        emit_mock.assert_awaited_once_with(Events.OBJECT_LISTED, [])

    async def test_bucket_not_found_raises_error(self):
        repo = self._build_repo()

        with (
            patch("app.services.bucket_get.ORMRepository", return_value=repo),
            patch(
                "app.services.bucket_get.load_bucket",
                new=AsyncMock(side_effect=S3BucketNotFoundError("/photos")),
            ),
        ):
            with self.assertRaises(S3BucketNotFoundError):
                await bucket_get(
                    session=self.session,
                    current_user=self.user,
                    bucket_name="photos",
                )

    async def test_access_denied_for_other_user_bucket(self):
        other_user = User(id=99, username="eve", is_root=False)
        repo = self._build_repo()

        with (
            patch("app.services.bucket_get.ORMRepository", return_value=repo),
            patch(
                "app.services.bucket_get.load_bucket",
                new=AsyncMock(side_effect=S3AccessDeniedError("/photos")),
            ),
        ):
            with self.assertRaises(S3AccessDeniedError):
                await bucket_get(
                    session=self.session,
                    current_user=other_user,
                    bucket_name="photos",
                )
