# tests/models/test_user_key.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402, F401
from app.models.bucket_tag import BucketTag  # noqa: E402, F401
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.objekt_metadata import ObjektMetadata  # noqa: E402, F401
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402, F401
from app.models.objekt_multipart_metadata import ObjektMultipartMetadata  # noqa: E402, F401
from app.models.objekt_multipart_tag import ObjektMultipartTag  # noqa: E402, F401
from app.models.objekt_multipart_part import ObjektMultipartPart  # noqa: E402, F401
from app.models.objekt_tag import ObjektTag  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
from app.models.objekt_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
from app.models.objekt_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402


class TestUserKeyModel(unittest.TestCase):

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
        self.assertEqual(UserKey.__tablename__, "users_keys")

    def test_persists_required_fields_and_defaults(self):
        key = UserKey(
            user_id=self.user.id,
            access_key_id="AKIAEXAMPLE000001",
            secret_access_key_encrypted="enc-secret",
        )
        self.session.add(key)
        self.session.commit()
        self.session.refresh(key)

        self.assertIsNotNone(key.id)
        self.assertEqual(key.user_id, self.user.id)
        self.assertEqual(key.access_key_id, "AKIAEXAMPLE000001")
        self.assertEqual(key.secret_access_key_encrypted, "enc-secret")
        self.assertTrue(key.is_enabled)
        self.assertIsInstance(key.created_at, int)
        self.assertIsNone(key.updated_at)

    def test_access_key_id_must_be_unique(self):
        self.session.add(
            UserKey(
                user_id=self.user.id,
                access_key_id="AKIAEXAMPLE000001",
                secret_access_key_encrypted="enc-1",
            ),
        )
        self.session.commit()

        other = User(username="bob")
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(
            UserKey(
                user_id=other.id,
                access_key_id="AKIAEXAMPLE000001",
                secret_access_key_encrypted="enc-2",
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_relationship_back_to_user(self):
        key = UserKey(
            user_id=self.user.id,
            access_key_id="AKIAEXAMPLE000001",
            secret_access_key_encrypted="enc-secret",
        )
        self.session.add(key)
        self.session.commit()

        loaded = self.session.scalar(
            select(UserKey)
            .where(UserKey.id == key.id)
            .options(selectinload(UserKey.user_key_user)),
        )

        self.assertEqual(loaded.user_key_user.id, self.user.id)
        self.assertEqual(loaded.user_key_user.username, "alice")

    def test_relationship_access_without_eager_load_raises(self):
        key = UserKey(
            user_id=self.user.id,
            access_key_id="AKIAEXAMPLE000001",
            secret_access_key_encrypted="enc-secret",
        )
        self.session.add(key)
        self.session.commit()

        loaded = self.session.scalar(
            select(UserKey).where(UserKey.id == key.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.user_key_user

    def test_cascade_delete_with_user(self):
        self.session.add(
            UserKey(
                user_id=self.user.id,
                access_key_id="AKIAEXAMPLE000001",
                secret_access_key_encrypted="enc-secret",
            ),
        )
        self.session.commit()

        # DB ON DELETE CASCADE; Core DELETE avoids ORM nulling the FK
        # under lazy="raise" without passive_deletes.
        self.session.execute(delete(User).where(User.id == self.user.id))
        self.session.commit()

        remaining = self.session.scalars(select(UserKey)).all()
        self.assertEqual(remaining, [])

    def test_is_enabled_independent_of_user(self):
        key = UserKey(
            user_id=self.user.id,
            access_key_id="AKIAEXAMPLE000001",
            secret_access_key_encrypted="enc-secret",
            is_enabled=False,
        )
        self.session.add(key)
        self.session.commit()
        self.session.refresh(key)
        self.session.refresh(self.user)

        self.assertFalse(key.is_enabled)
        self.assertTrue(self.user.is_enabled)
