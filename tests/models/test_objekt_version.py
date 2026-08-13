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
            "bucket_id": self.bucket.id,
            "objekt_id": self.objekt.id,
            "user_id": self.user.id,
            "object_key": self.objekt.object_key,
            "version_id": "a" * 32,
            "size_bytes": 1,
            "etag": "b" * 32,
        }
        defaults.update(kwargs)
        return ObjektVersion(**defaults)

    def test_tablename(self):
        self.assertEqual(ObjektVersion.__tablename__, "objekts_versions")

    def test_persists_required_fields_and_defaults(self):
        version = self._version(
            version_id="c" * 32,
            size_bytes=1024,
            etag="d41d8cd98f00b204e9800998ecf8427e",
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertIsNotNone(version.id)
        self.assertEqual(version.bucket_id, self.bucket.id)
        self.assertEqual(version.objekt_id, self.objekt.id)
        self.assertEqual(version.user_id, self.user.id)
        self.assertEqual(version.object_key, "a.txt")
        self.assertEqual(version.version_id, "c" * 32)
        self.assertEqual(version.size_bytes, 1024)
        self.assertEqual(version.etag, "d41d8cd98f00b204e9800998ecf8427e")
        self.assertEqual(version.content_type, "application/octet-stream")
        self.assertFalse(version.is_deleted)
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
                object_key="other.txt",
                version_id="a" * 32,
                etag="c" * 32,
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_deleted_and_lock_fields(self):
        version = self._version(
            version_id="d" * 32,
            size_bytes=0,
            etag="",
            is_deleted=True,
            lock_mode="COMPLIANCE",
            retain_until=1_704_067_200,
            legal_hold=True,
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertTrue(version.is_deleted)
        self.assertEqual(version.lock_mode, "COMPLIANCE")
        self.assertEqual(version.retain_until, 1_704_067_200)
        self.assertTrue(version.legal_hold)

    def test_relationship_back_to_objekt(self):
        version = self._version(version_id="e" * 32)
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertEqual(version.objekts_versions_objekts.id, self.objekt.id)
        self.assertEqual(
            version.objekts_versions_objekts.object_key,
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
            .options(selectinload(Objekt.objekts_versions)),
        )

        ids = sorted(v.version_id for v in loaded.objekts_versions)
        self.assertEqual(ids, ["a" * 32, "b" * 32])

    def test_relationship_back_to_bucket(self):
        version = self._version(version_id="e" * 32)
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertEqual(version.objekts_versions_buckets.id, self.bucket.id)

    def test_relationship_back_to_user(self):
        version = self._version(version_id="f" * 32)
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertEqual(version.objekts_versions_users.id, self.user.id)

    def test_bucket_relationship_to_versions(self):
        other = Objekt(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            object_key="b.txt",
            size_bytes=2,
            etag="e" * 32,
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(self._version(version_id="a" * 32))
        self.session.add(
            self._version(
                objekt_id=other.id,
                object_key="b.txt",
                version_id="b" * 32,
                etag="b" * 32,
            ),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket)
            .where(Bucket.id == self.bucket.id)
            .options(selectinload(Bucket.bucket_objekts_versions)),
        )

        keys = sorted(v.object_key for v in loaded.bucket_objekts_versions)
        self.assertEqual(keys, ["a.txt", "b.txt"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt).where(Objekt.id == self.objekt.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.objekts_versions

    def test_bucket_relationship_access_without_eager_load_raises(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket).where(Bucket.id == self.bucket.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.bucket_objekts_versions

    def test_cascade_delete_with_objekt(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        self.session.delete(self.objekt)
        self.session.commit()

        remaining = self.session.scalars(select(ObjektVersion)).all()
        self.assertEqual(remaining, [])

    def test_cascade_delete_with_bucket(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        self.session.delete(self.bucket)
        self.session.commit()

        remaining = self.session.scalars(select(ObjektVersion)).all()
        self.assertEqual(remaining, [])
