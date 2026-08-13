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
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
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

    def test_tablename(self):
        self.assertEqual(Bucket.__tablename__, "buckets")

    def test_persists_required_fields_and_defaults(self):
        bucket = Bucket(user_id=self.user.id, bucket_name="photos")
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertIsNotNone(bucket.id)
        self.assertEqual(bucket.user_id, self.user.id)
        self.assertEqual(bucket.bucket_name, "photos")
        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_DISABLED)
        self.assertIsInstance(bucket.created_at, int)
        self.assertIsNone(bucket.updated_at)

    def test_versioning_status_can_be_set(self):
        bucket = Bucket(
            user_id=self.user.id,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
        )
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertEqual(bucket.versioning_status, BUCKET_VERSIONING_ENABLED)

    def test_bucket_name_must_be_unique(self):
        self.session.add(Bucket(user_id=self.user.id, bucket_name="photos"))
        self.session.commit()

        other = User(username="bob")
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(Bucket(user_id=other.id, bucket_name="photos"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_relationship_back_to_user(self):
        bucket = Bucket(user_id=self.user.id, bucket_name="photos")
        self.session.add(bucket)
        self.session.commit()
        self.session.refresh(bucket)

        self.assertEqual(bucket.buckets_users.id, self.user.id)
        self.assertEqual(bucket.buckets_users.username, "alice")

    def test_user_relationship_to_buckets(self):
        self.session.add(Bucket(user_id=self.user.id, bucket_name="photos"))
        self.session.add(Bucket(user_id=self.user.id, bucket_name="docs"))
        self.session.commit()

        loaded = self.session.scalar(
            select(User)
            .where(User.id == self.user.id)
            .options(selectinload(User.buckets)),
        )

        names = sorted(bucket.bucket_name for bucket in loaded.buckets)
        self.assertEqual(names, ["docs", "photos"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(Bucket(user_id=self.user.id, bucket_name="photos"))
        self.session.commit()

        loaded = self.session.scalar(
            select(User).where(User.id == self.user.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.buckets

    def test_cascade_delete_with_user(self):
        self.session.add(Bucket(user_id=self.user.id, bucket_name="photos"))
        self.session.commit()

        self.session.delete(self.user)
        self.session.commit()

        remaining = self.session.scalars(select(Bucket)).all()
        self.assertEqual(remaining, [])
