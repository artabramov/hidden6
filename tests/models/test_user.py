# tests/models/test_user.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.bucket_tag import BucketTag  # noqa: E402, F401
from app.models.object import Objekt  # noqa: E402, F401
from app.models.object_metadata import ObjectMetadata  # noqa: E402, F401
from app.models.object_multipart import ObjectMultipart  # noqa: E402, F401
from app.models.object_multipart_metadata import ObjectMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_tag import ObjectMultipartTag  # noqa: E402, F401
from app.models.object_multipart_part import ObjectMultipartPart  # noqa: E402, F401
from app.models.object_tag import ObjectTag  # noqa: E402, F401
from app.models.object_version import ObjectVersion  # noqa: E402, F401
from app.models.object_version_metadata import ObjectVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import ObjectVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402


class TestUserModel(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_connection, _connection_record):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_tablename(self):
        self.assertEqual(User.__tablename__, "users")

    def test_persists_required_fields_and_defaults(self):
        user = User(username="alice")
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        self.assertIsNotNone(user.id)
        self.assertEqual(user.username, "alice")
        self.assertTrue(user.is_enabled)
        self.assertFalse(user.is_root)
        self.assertIsInstance(user.created_at, int)
        self.assertIsNone(user.updated_at)

    def test_username_must_be_unique(self):
        self.session.add(User(username="alice"))
        self.session.commit()

        self.session.add(User(username="alice"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_root_flag_can_be_set(self):
        user = User(username="root", is_root=True)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)

        self.assertTrue(user.is_root)

    def test_relationships_to_keys_and_buckets(self):
        user = User(username="alice")
        self.session.add(user)
        self.session.flush()

        key = UserKey(
            user_id=user.id,
            access_key_id="AKIAEXAMPLE000001",
            secret_access_key_encrypted="enc-secret",
        )
        bucket = Bucket(user_id=user.id, bucket_name="photos")
        self.session.add_all([key, bucket])
        self.session.commit()

        loaded = self.session.scalar(
            select(User)
            .where(User.id == user.id)
            .options(
                selectinload(User.user_keys),
                selectinload(User.user_buckets),
            ),
        )

        self.assertEqual(len(loaded.user_keys), 1)
        self.assertEqual(len(loaded.user_buckets), 1)
        self.assertEqual(
            loaded.user_keys[0].access_key_id,
            "AKIAEXAMPLE000001",
        )
        self.assertEqual(loaded.user_buckets[0].bucket_name, "photos")

    def test_relationship_access_without_eager_load_raises(self):
        user = User(username="alice")
        self.session.add(user)
        self.session.commit()

        loaded = self.session.scalar(
            select(User).where(User.username == "alice"),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.user_keys

        with self.assertRaises(InvalidRequestError):
            _ = loaded.user_buckets

    def test_select_by_username(self):
        self.session.add(User(username="bob"))
        self.session.commit()

        found = self.session.scalar(
            select(User).where(User.username == "bob"),
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.username, "bob")
