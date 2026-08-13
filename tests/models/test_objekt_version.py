# tests/models/test_objekt_version.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjektVersionModel(unittest.TestCase):

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

        self.bucket = Bucket(
            user_id=self.user.id,
            bucket_name="photos",
        )
        self.session.add(self.bucket)
        self.session.commit()
        self.session.refresh(self.bucket)

        self.objekt = Objekt(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            object_key="a.txt",
            size_bytes=10,
            etag="c" * 32,
        )
        self.session.add(self.objekt)
        self.session.commit()
        self.session.refresh(self.objekt)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _version(self, **kwargs) -> ObjektVersion:
        defaults = {
            "objekt_id": self.objekt.id,
            "user_id": self.user.id,
            "version_id": "a" * 32,
        }
        defaults.update(kwargs)
        return ObjektVersion(**defaults)

    def test_tablename(self):
        self.assertEqual(ObjektVersion.__tablename__, "objekts_versions")

    def test_persists_required_fields_and_defaults(self):
        version = self._version(version_id="c" * 32)
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertIsNotNone(version.id)
        self.assertEqual(version.objekt_id, self.objekt.id)
        self.assertEqual(version.user_id, self.user.id)
        self.assertEqual(version.version_id, "c" * 32)
        self.assertIsNone(version.size_bytes)
        self.assertIsNone(version.etag)
        self.assertIsNone(version.content_type)
        self.assertFalse(version.delete_marker)
        self.assertIsNone(version.lock_mode)
        self.assertIsNone(version.retain_until)
        self.assertFalse(version.legal_hold)
        self.assertIsInstance(version.created_at, int)
        self.assertIsNone(version.updated_at)

    def test_same_objekt_may_have_many_versions(self):
        self.session.add(self._version(version_id="a" * 32, etag="a" * 32))
        self.session.add(
            self._version(
                version_id="b" * 32,
                size_bytes=2,
                etag="b" * 32,
            ),
        )
        self.session.commit()

        rows = self.session.scalars(
            select(ObjektVersion).where(
                ObjektVersion.objekt_id == self.objekt.id,
            ),
        ).all()
        self.assertEqual(len(rows), 2)

    def test_version_id_must_be_unique(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        other = Objekt(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            object_key="other.txt",
            size_bytes=1,
            etag="d" * 32,
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(
            self._version(
                objekt_id=other.id,
                version_id="a" * 32,
                etag="c" * 32,
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_delete_marker_and_lock_fields(self):
        version = self._version(
            version_id="d" * 32,
            delete_marker=True,
            lock_mode="COMPLIANCE",
            retain_until=1_704_067_200,
            legal_hold=True,
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertTrue(version.delete_marker)
        self.assertIsNone(version.size_bytes)
        self.assertIsNone(version.etag)
        self.assertIsNone(version.content_type)
        self.assertEqual(version.lock_mode, "COMPLIANCE")
        self.assertEqual(version.retain_until, 1_704_067_200)
        self.assertTrue(version.legal_hold)

    def test_relationship_back_to_objekt(self):
        version = self._version(version_id="e" * 32)
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertEqual(version.objekt_version_objekt.id, self.objekt.id)
        self.assertEqual(
            version.objekt_version_objekt.object_key,
            "a.txt",
        )

    def test_objekt_relationship_to_versions(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.add(
            self._version(version_id="b" * 32, size_bytes=2, etag="b" * 32),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt)
            .where(Objekt.id == self.objekt.id)
            .options(selectinload(Objekt.objekt_versions)),
        )

        ids = sorted(v.version_id for v in loaded.objekt_versions)
        self.assertEqual(ids, ["a" * 32, "b" * 32])

    def test_relationship_back_to_user(self):
        version = self._version(version_id="f" * 32)
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertEqual(version.objekt_version_user.id, self.user.id)

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt).where(Objekt.id == self.objekt.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.objekt_versions

    def test_objekt_delete_is_restricted(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        self.session.delete(self.objekt)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_bucket_delete_is_restricted(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        self.session.delete(self.bucket)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_uploader_delete_is_restricted(self):
        root = User(username="root", is_root=True)
        self.session.add(root)
        self.session.commit()
        self.session.refresh(root)

        self.session.add(self._version(version_id="a" * 32, user_id=root.id))
        self.session.commit()

        self.session.delete(root)
        with self.assertRaises(IntegrityError):
            self.session.commit()
