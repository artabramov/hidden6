# tests/models/test_object_version.py
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
from app.models.objekt import Objekt  # noqa: E402
from app.models.object_metadata import ObjectMetadata  # noqa: E402, F401
from app.models.object_multipart import ObjectMultipart  # noqa: E402, F401
from app.models.object_multipart_metadata import ObjectMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_tag import ObjectMultipartTag  # noqa: E402, F401
from app.models.object_multipart_part import ObjectMultipartPart  # noqa: E402, F401
from app.models.object_tag import ObjectTag  # noqa: E402, F401
from app.models.object_version import ObjectVersion  # noqa: E402
from app.models.object_version_metadata import ObjectVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import ObjectVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjectVersionModel(unittest.TestCase):

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
            content_type="text/plain",
        )
        self.session.add(self.objekt)
        self.session.commit()
        self.session.refresh(self.objekt)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _version(self, **kwargs) -> ObjectVersion:
        defaults = {
            "object_id": self.objekt.id,
            "user_id": self.user.id,
            "version_id": "a" * 32,
            "modified_at": 1_704_067_200,
            "size_bytes": 1,
            "etag": "b" * 32,
            "content_type": "text/plain",
        }
        defaults.update(kwargs)
        return ObjectVersion(**defaults)

    def _delete_marker(self, **kwargs) -> ObjectVersion:
        defaults = {
            "delete_marker": True,
            "size_bytes": None,
            "etag": None,
            "content_type": None,
        }
        defaults.update(kwargs)
        return self._version(**defaults)

    def _assert_rejects(self, version):
        self.session.add(version)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_tablename(self):
        self.assertEqual(ObjectVersion.__tablename__, "objects_versions")

    def test_persists_required_fields_and_defaults(self):
        version = self._version(
            version_id="c" * 32,
            modified_at=1_704_153_600,
            size_bytes=1024,
            etag="d41d8cd98f00b204e9800998ecf8427e",
            content_type="image/png",
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertIsNotNone(version.id)
        self.assertEqual(version.object_id, self.objekt.id)
        self.assertEqual(version.user_id, self.user.id)
        self.assertEqual(version.version_id, "c" * 32)
        self.assertEqual(version.modified_at, 1_704_153_600)
        self.assertEqual(version.size_bytes, 1024)
        self.assertEqual(version.etag, "d41d8cd98f00b204e9800998ecf8427e")
        self.assertEqual(version.content_type, "image/png")
        self.assertFalse(version.delete_marker)
        self.assertIsNone(version.lock_mode)
        self.assertIsNone(version.retain_until)
        self.assertFalse(version.legal_hold)
        self.assertIsInstance(version.created_at, int)

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
            select(ObjectVersion).where(
                ObjectVersion.object_id == self.objekt.id,
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
            content_type="text/plain",
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(
            self._version(
                object_id=other.id,
                version_id="a" * 32,
                etag="c" * 32,
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_delete_marker_has_no_payload(self):
        version = self._delete_marker(version_id="d" * 32)
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertTrue(version.delete_marker)
        self.assertIsNone(version.size_bytes)
        self.assertIsNone(version.etag)
        self.assertIsNone(version.content_type)
        self.assertIsNone(version.lock_mode)
        self.assertIsNone(version.retain_until)
        self.assertFalse(version.legal_hold)

    def test_object_lock_fields(self):
        version = self._version(
            version_id="d" * 32,
            lock_mode="COMPLIANCE",
            retain_until=1_704_067_200,
            legal_hold=True,
        )
        self.session.add(version)
        self.session.commit()
        self.session.refresh(version)

        self.assertFalse(version.delete_marker)
        self.assertEqual(version.lock_mode, "COMPLIANCE")
        self.assertEqual(version.retain_until, 1_704_067_200)
        self.assertTrue(version.legal_hold)

    def test_payload_required_when_not_delete_marker(self):
        self._assert_rejects(self._version(etag=None))

    def test_payload_forbidden_on_delete_marker(self):
        self._assert_rejects(self._delete_marker(etag="a" * 32))

    def test_delete_marker_cannot_have_object_lock(self):
        self._assert_rejects(
            self._delete_marker(
                lock_mode="GOVERNANCE",
                retain_until=1_704_067_200,
            ),
        )

    def test_delete_marker_cannot_have_legal_hold(self):
        self._assert_rejects(self._delete_marker(legal_hold=True))

    def test_lock_mode_requires_retain_until(self):
        self._assert_rejects(self._version(lock_mode="GOVERNANCE"))

    def test_lock_mode_must_be_governance_or_compliance(self):
        self._assert_rejects(
            self._version(
                lock_mode="INVALID",
                retain_until=1_704_067_200,
            ),
        )

    def test_size_bytes_must_be_nonnegative(self):
        self._assert_rejects(self._version(size_bytes=-1))

    def test_relationship_back_to_objekt(self):
        version = self._version(version_id="e" * 32)
        self.session.add(version)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectVersion)
            .where(ObjectVersion.id == version.id)
            .options(selectinload(ObjectVersion.object_version_object)),
        )

        self.assertEqual(loaded.object_version_object.id, self.objekt.id)
        self.assertEqual(
            loaded.object_version_object.object_key,
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
            .options(selectinload(Objekt.object_versions)),
        )

        ids = sorted(v.version_id for v in loaded.object_versions)
        self.assertEqual(ids, ["a" * 32, "b" * 32])

    def test_relationship_back_to_user(self):
        version = self._version(version_id="f" * 32)
        self.session.add(version)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectVersion)
            .where(ObjectVersion.id == version.id)
            .options(selectinload(ObjectVersion.object_version_user)),
        )

        self.assertEqual(loaded.object_version_user.id, self.user.id)

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._version(version_id="a" * 32))
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt).where(Objekt.id == self.objekt.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_versions

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
