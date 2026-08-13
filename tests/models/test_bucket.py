# tests/models/test_bucket.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.constants import (  # noqa: E402
    BUCKET_VERSIONING_DISABLED,
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.objekt_metadata import ObjektMetadata  # noqa: E402, F401
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402, F401
from app.models.objekt_multipart_metadata import ObjektMultipartMetadata  # noqa: E402, F401
from app.models.objekt_multipart_tag import ObjektMultipartTag  # noqa: E402, F401
from app.models.objekt_tag import ObjektTag  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
from app.models.objekt_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
from app.models.objekt_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestBucketModel(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.user = User(username="alice")
        self.session.add(self.user)
        self.session.commit()
        self.session.refresh(self.user)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _bucket(self, **kwargs) -> Bucket:
        defaults = {
            "user_id": self.user.id,
            "bucket_name": "photos",
        }
        defaults.update(kwargs)
        return Bucket(**defaults)

    def _lock_bucket(self, **kwargs) -> Bucket:
        defaults = {
            "versioning_status": BUCKET_VERSIONING_ENABLED,
            "object_lock_enabled": True,
        }
        defaults.update(kwargs)
        return self._bucket(**defaults)

    def _assert_rejects(self, bucket):
        self.session.add(bucket)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_tablename(self):
        self.assertEqual(Bucket.__tablename__, "buckets")

    def test_persists_required_fields_and_defaults(self):
        bucket = self._bucket()
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertIsNotNone(bucket.id)
        self.assertEqual(bucket.user_id, self.user.id)
        self.assertEqual(bucket.bucket_name, "photos")
        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_DISABLED)
        self.assertFalse(bucket.object_lock_enabled)
        self.assertIsNone(bucket.default_lock_mode)
        self.assertIsNone(bucket.default_retention_days)
        self.assertIsNone(bucket.default_retention_years)
        self.assertIsInstance(bucket.created_at, int)

    def test_versioning_status_can_be_set(self):
        bucket = self._bucket(versioning_status=BUCKET_VERSIONING_ENABLED)
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)

    def test_versioning_status_can_be_suspended(self):
        bucket = self._bucket(versioning_status=BUCKET_VERSIONING_SUSPENDED)
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_SUSPENDED)

    def test_object_lock_requires_versioning_enabled(self):
        bucket = self._lock_bucket()
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertTrue(bucket.object_lock_enabled)
        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)
        self.assertIsNone(bucket.default_lock_mode)

    def test_default_retention_days(self):
        bucket = self._lock_bucket(
            default_lock_mode="GOVERNANCE",
            default_retention_days=30,
        )
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertEqual(bucket.default_lock_mode, "GOVERNANCE")
        self.assertEqual(bucket.default_retention_days, 30)
        self.assertIsNone(bucket.default_retention_years)

    def test_default_retention_years(self):
        bucket = self._lock_bucket(
            default_lock_mode="COMPLIANCE",
            default_retention_years=1,
        )
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertEqual(bucket.default_lock_mode, "COMPLIANCE")
        self.assertIsNone(bucket.default_retention_days)
        self.assertEqual(bucket.default_retention_years, 1)

    def test_bucket_name_must_be_unique(self):
        self.session.add(self._bucket())
        self.session.commit()

        other = User(username="bob")
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(Bucket(user_id=other.id, bucket_name="photos"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_versioning_status_must_be_known(self):
        self._assert_rejects(self._bucket(versioning_status="Invalid"))

    def test_object_lock_forbidden_when_versioning_disabled(self):
        self._assert_rejects(self._bucket(object_lock_enabled=True))

    def test_object_lock_forbidden_when_versioning_suspended(self):
        self._assert_rejects(
            self._bucket(
                versioning_status=BUCKET_VERSIONING_SUSPENDED,
                object_lock_enabled=True,
            ),
        )

    def test_default_retention_requires_object_lock(self):
        self._assert_rejects(
            self._bucket(
                default_lock_mode="GOVERNANCE",
                default_retention_days=30,
            ),
        )

    def test_default_lock_mode_requires_period(self):
        self._assert_rejects(self._lock_bucket(default_lock_mode="GOVERNANCE"))

    def test_default_retention_days_and_years_are_exclusive(self):
        self._assert_rejects(
            self._lock_bucket(
                default_lock_mode="GOVERNANCE",
                default_retention_days=30,
                default_retention_years=1,
            ),
        )

    def test_default_retention_days_must_be_positive(self):
        self._assert_rejects(
            self._lock_bucket(
                default_lock_mode="GOVERNANCE",
                default_retention_days=0,
            ),
        )

    def test_default_retention_years_must_be_positive(self):
        self._assert_rejects(
            self._lock_bucket(
                default_lock_mode="COMPLIANCE",
                default_retention_years=0,
            ),
        )

    def test_default_lock_mode_must_be_governance_or_compliance(self):
        self._assert_rejects(
            self._lock_bucket(
                default_lock_mode="INVALID",
                default_retention_days=30,
            ),
        )

    def test_relationship_back_to_user(self):
        bucket = self._bucket()
        self.session.add(bucket)
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket)
            .where(Bucket.id == bucket.id)
            .options(selectinload(Bucket.bucket_user)),
        )

        self.assertEqual(loaded.bucket_user.id, self.user.id)
        self.assertEqual(loaded.bucket_user.username, "alice")

    def test_user_relationship_to_buckets(self):
        self.session.add(self._bucket())
        self.session.add(self._bucket(bucket_name="docs"))
        self.session.commit()

        loaded = self.session.scalar(
            select(User)
            .where(User.id == self.user.id)
            .options(selectinload(User.user_buckets)),
        )

        names = sorted(bucket.bucket_name for bucket in loaded.user_buckets)
        self.assertEqual(names, ["docs", "photos"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._bucket())
        self.session.commit()

        loaded_user = self.session.scalar(
            select(User).where(User.id == self.user.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded_user.user_buckets

        loaded_bucket = self.session.scalar(
            select(Bucket).where(Bucket.bucket_name == "photos"),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded_bucket.bucket_user

    def test_user_delete_is_restricted(self):
        self.session.add(self._bucket())
        self.session.commit()

        self.session.delete(self.user)
        with self.assertRaises(IntegrityError):
            self.session.commit()
