# tests/routers/test_bucket_get.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import status

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import (  # noqa: E402
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
    S3_XMLNS,
)
from app.db.engine import load_all_models  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.object import S3Object  # noqa: E402
from app.models.user import User  # noqa: E402
from app.routers.bucket_get import bucket_get_router  # noqa: E402

load_all_models()


class TestBucketGetRouter(unittest.IsolatedAsyncioTestCase):
    async def test_returns_200_with_list_bucket_xml(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()
        objekts = [
            S3Object(
                id=3,
                bucket_id=7,
                user_id=1,
                object_key="2024/cat.png",
                size_bytes=12,
                etag="etag123",
                content_type="image/png",
                created_at=1_704_067_200,
                modified_at=1_704_067_200,
            ),
        ]

        with (
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
                return_value=objekts,
            ) as mock_list,
            patch(
                "app.routers.bucket_get.bucket_versioning_retrieve",
                new_callable=AsyncMock,
            ) as mock_versioning,
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
            ) as mock_lock,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                prefix="2024/",
                max_keys=100,
            )

        mock_list.assert_awaited_once_with(
            session=session,
            current_user=user,
            bucket_name="photos",
            prefix="2024/",
            max_keys=100,
        )
        mock_versioning.assert_not_awaited()
        mock_lock.assert_not_awaited()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "application/xml")

        body = response.body.decode()
        self.assertIn("<ListBucketResult", body)
        self.assertIn("<Name>photos</Name>", body)
        self.assertIn("<Prefix>2024/</Prefix>", body)
        self.assertIn("<MaxKeys>100</MaxKeys>", body)
        self.assertIn("<Key>2024/cat.png</Key>", body)
        self.assertIn("<ETag>&quot;etag123&quot;</ETag>", body)

    async def test_returns_empty_contents_xml(self):
        user = User(id=2, username="bob", is_root=False)
        session = MagicMock()

        with (
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_list,
            patch(
                "app.routers.bucket_get.bucket_versioning_retrieve",
                new_callable=AsyncMock,
            ) as mock_versioning,
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
            ) as mock_lock,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
            )

        mock_list.assert_awaited_once_with(
            session=session,
            current_user=user,
            bucket_name="photos",
            prefix="",
            max_keys=1000,
        )
        mock_versioning.assert_not_awaited()
        mock_lock.assert_not_awaited()
        body = response.body.decode()
        self.assertIn("<KeyCount>0</KeyCount>", body)
        self.assertNotIn("<Contents>", body)

    async def test_returns_versioning_xml_when_enabled(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()

        with (
            patch(
                "app.routers.bucket_get.bucket_versioning_retrieve",
                new_callable=AsyncMock,
                return_value=BUCKET_VERSIONING_ENABLED,
            ) as mock_versioning,
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
            ) as mock_list,
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
            ) as mock_lock,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                versioning="",
            )

        mock_versioning.assert_awaited_once_with(
            session=session,
            current_user=user,
            bucket_name="photos",
        )
        mock_list.assert_not_awaited()
        mock_lock.assert_not_awaited()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "application/xml")

        body = response.body.decode()
        self.assertIn("<VersioningConfiguration", body)
        self.assertIn(f'xmlns="{S3_XMLNS}"', body)
        self.assertIn(
            f"<Status>{BUCKET_VERSIONING_ENABLED}</Status>",
            body,
        )

    async def test_returns_versioning_xml_when_suspended(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()

        with (
            patch(
                "app.routers.bucket_get.bucket_versioning_retrieve",
                new_callable=AsyncMock,
                return_value=BUCKET_VERSIONING_SUSPENDED,
            ),
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
            ) as mock_list,
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
            ) as mock_lock,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                versioning="",
            )

        mock_list.assert_not_awaited()
        mock_lock.assert_not_awaited()
        body = response.body.decode()
        self.assertIn(
            f"<Status>{BUCKET_VERSIONING_SUSPENDED}</Status>",
            body,
        )

    async def test_returns_versioning_xml_without_status(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()

        with (
            patch(
                "app.routers.bucket_get.bucket_versioning_retrieve",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
            ) as mock_list,
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
            ) as mock_lock,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                versioning="",
            )

        mock_list.assert_not_awaited()
        mock_lock.assert_not_awaited()
        body = response.body.decode()
        self.assertIn("<VersioningConfiguration", body)
        self.assertNotIn("<Status>", body)

    async def test_returns_object_lock_xml_without_default_rule(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()
        bucket = Bucket(
            id=7,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
        )

        with (
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
                return_value=bucket,
            ) as mock_lock,
            patch(
                "app.routers.bucket_get.bucket_versioning_retrieve",
                new_callable=AsyncMock,
            ) as mock_versioning,
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
            ) as mock_list,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                object_lock="",
            )

        mock_lock.assert_awaited_once_with(
            session=session,
            current_user=user,
            bucket_name="photos",
        )
        mock_versioning.assert_not_awaited()
        mock_list.assert_not_awaited()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.media_type, "application/xml")

        body = response.body.decode()
        self.assertIn("<ObjectLockConfiguration", body)
        self.assertIn(f'xmlns="{S3_XMLNS}"', body)
        self.assertIn("<ObjectLockEnabled>Enabled</ObjectLockEnabled>", body)
        self.assertNotIn("<Rule>", body)

    async def test_returns_object_lock_xml_with_default_retention(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()
        bucket = Bucket(
            id=7,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
            default_lock_mode="GOVERNANCE",
            default_retention_days=10,
        )

        with (
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
                return_value=bucket,
            ),
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
            ) as mock_list,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                object_lock="",
            )

        mock_list.assert_not_awaited()
        body = response.body.decode()
        self.assertIn("<Mode>GOVERNANCE</Mode>", body)
        self.assertIn("<Days>10</Days>", body)

    async def test_object_lock_query_takes_precedence_over_versioning(self):
        user = User(id=1, username="alice", is_root=False)
        session = MagicMock()
        bucket = Bucket(
            id=7,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
        )

        with (
            patch(
                "app.routers.bucket_get.bucket_object_lock_retrieve",
                new_callable=AsyncMock,
                return_value=bucket,
            ) as mock_lock,
            patch(
                "app.routers.bucket_get.bucket_versioning_retrieve",
                new_callable=AsyncMock,
            ) as mock_versioning,
            patch(
                "app.routers.bucket_get.bucket_get",
                new_callable=AsyncMock,
            ) as mock_list,
        ):
            response = await bucket_get_router(
                bucket_name="photos",
                session=session,
                current_user=user,
                object_lock="",
                versioning="",
            )

        mock_lock.assert_awaited_once()
        mock_versioning.assert_not_awaited()
        mock_list.assert_not_awaited()
        body = response.body.decode()
        self.assertIn("<ObjectLockConfiguration", body)
        self.assertNotIn("<VersioningConfiguration", body)
