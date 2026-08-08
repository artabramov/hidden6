# tests/models/test_user.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402
from app.models.user_policy import UserPolicy  # noqa: E402


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

    def test_relationships_to_keys_and_policies(self):
        user = User(username="alice")
        self.session.add(user)
        self.session.flush()

        key = UserKey(
            user_id=user.id,
            access_key_id="AKIAEXAMPLE000001",
            secret_access_key_encrypted="enc-secret",
        )
        policy = UserPolicy(
            user_id=user.id,
            policy_name="readonly",
            policy_document={
                "Version": "2012-10-17",
                "Statement": [],
            },
        )
        self.session.add_all([key, policy])
        self.session.commit()
        self.session.refresh(user)

        self.assertEqual(len(user.user_keys), 1)
        self.assertEqual(len(user.user_policies), 1)
        self.assertEqual(user.user_keys[0].access_key_id, "AKIAEXAMPLE000001")
        self.assertEqual(user.user_policies[0].policy_name, "readonly")

    def test_select_by_username(self):
        self.session.add(User(username="bob"))
        self.session.commit()

        found = self.session.scalar(
            select(User).where(User.username == "bob"),
        )
        self.assertIsNotNone(found)
        self.assertEqual(found.username, "bob")
