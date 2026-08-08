# tests/models/test_user_policy.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_policy import UserPolicy  # noqa: E402


class TestUserPolicyModel(unittest.TestCase):

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

        self.policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::bucket/*"],
                },
            ],
        }

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_tablename(self):
        self.assertEqual(UserPolicy.__tablename__, "users_policies")

    def test_persists_required_fields_and_defaults(self):
        policy = UserPolicy(
            user_id=self.user.id,
            policy_name="readonly",
            policy_document=self.policy_document,
        )
        self.session.add(policy)
        self.session.commit()
        self.session.refresh(policy)

        self.assertIsNotNone(policy.id)
        self.assertEqual(policy.user_id, self.user.id)
        self.assertEqual(policy.policy_name, "readonly")
        self.assertEqual(policy.policy_document, self.policy_document)
        self.assertTrue(policy.is_enabled)
        self.assertIsInstance(policy.created_at, int)
        self.assertIsNone(policy.updated_at)

    def test_policy_document_json_roundtrip(self):
        policy = UserPolicy(
            user_id=self.user.id,
            policy_name="readonly",
            policy_document=self.policy_document,
        )
        self.session.add(policy)
        self.session.commit()

        loaded = self.session.scalar(
            select(UserPolicy).where(UserPolicy.policy_name == "readonly"),
        )
        self.assertEqual(
            loaded.policy_document["Statement"][0]["Action"],
            ["s3:GetObject"],
        )

    def test_policy_name_unique_per_user(self):
        self.session.add(
            UserPolicy(
                user_id=self.user.id,
                policy_name="readonly",
                policy_document=self.policy_document,
            ),
        )
        self.session.commit()

        self.session.add(
            UserPolicy(
                user_id=self.user.id,
                policy_name="readonly",
                policy_document={"Version": "2012-10-17", "Statement": []},
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_policy_name_allowed_for_different_users(self):
        other = User(username="bob")
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add_all(
            [
                UserPolicy(
                    user_id=self.user.id,
                    policy_name="readonly",
                    policy_document=self.policy_document,
                ),
                UserPolicy(
                    user_id=other.id,
                    policy_name="readonly",
                    policy_document=self.policy_document,
                ),
            ],
        )
        self.session.commit()

        names = self.session.scalars(select(UserPolicy.policy_name)).all()
        self.assertEqual(names.count("readonly"), 2)

    def test_relationship_back_to_user(self):
        policy = UserPolicy(
            user_id=self.user.id,
            policy_name="readonly",
            policy_document=self.policy_document,
        )
        self.session.add(policy)
        self.session.commit()
        self.session.refresh(policy)

        self.assertEqual(policy.user_policy_user.id, self.user.id)
        self.assertEqual(policy.user_policy_user.username, "alice")

    def test_cascade_delete_with_user(self):
        self.session.add(
            UserPolicy(
                user_id=self.user.id,
                policy_name="readonly",
                policy_document=self.policy_document,
            ),
        )
        self.session.commit()

        self.session.delete(self.user)
        self.session.commit()

        remaining = self.session.scalars(select(UserPolicy)).all()
        self.assertEqual(remaining, [])
