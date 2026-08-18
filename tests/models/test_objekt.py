# tests/models/test_objekt.py
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
from app.models.object_version import ObjectVersion  # noqa: E402, F401
from app.models.object_version_metadata import ObjectVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import ObjectVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjektModel(unittest.TestCase):

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

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _objekt(self, **kwargs) -> Objekt:
        defaults = {
            "bucket_id": self.bucket.id,
            "user_id": self.user.id,
            "object_key": "a.txt",
            "size_bytes": 1,
            "etag": "a" * 32,
            "content_type": "text/plain",
        }
        defaults.update(kwargs)
        return Objekt(**defaults)

    def _delete_marker(self, **kwargs) -> Objekt:
        defaults = {
            "delete_marker": True,
            "size_bytes": None,
            "etag": None,
            "content_type": None,
        }
        defaults.update(kwargs)
        return self._objekt(**defaults)

    def _assert_rejects(self, objekt):
        self.session.add(objekt)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_tablename(self):
        self.assertEqual(Objekt.__tablename__, "objekts")

    def test_persists_required_fields_and_defaults(self):
        objekt = self._objekt(
            object_key="album/a.jpg",
            size_bytes=1024,
            etag="d41d8cd98f00b204e9800998ecf8427e",
            content_type="image/jpeg",
        )
        self.session.add(objekt)
        self.session.commit()
        self.session.refresh(objekt)

        self.assertIsNotNone(objekt.id)
        self.assertEqual(objekt.bucket_id, self.bucket.id)
        self.assertEqual(objekt.user_id, self.user.id)
        self.assertEqual(objekt.object_key, "album/a.jpg")
        self.assertEqual(objekt.size_bytes, 1024)
        self.assertEqual(objekt.etag, "d41d8cd98f00b204e9800998ecf8427e")
        self.assertEqual(objekt.content_type, "image/jpeg")
        self.assertIsNone(objekt.version_id)
        self.assertFalse(objekt.delete_marker)
        self.assertIsNone(objekt.lock_mode)
        self.assertIsNone(objekt.retain_until)
        self.assertFalse(objekt.legal_hold)
        self.assertIsInstance(objekt.created_at, int)
        self.assertIsInstance(objekt.modified_at, int)

    def test_object_key_unique_per_bucket(self):
        self.session.add(self._objekt(object_key="same.txt", etag="a" * 32))
        self.session.commit()

        self.session.add(
            self._objekt(
                object_key="same.txt",
                size_bytes=2,
                etag="b" * 32,
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_key_allowed_in_different_buckets(self):
        other = Bucket(user_id=self.user.id, bucket_name="docs")
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(self._objekt(object_key="readme.txt", etag="a" * 32))
        self.session.add(
            self._objekt(
                bucket_id=other.id,
                object_key="readme.txt",
                size_bytes=2,
                etag="b" * 32,
            ),
        )
        self.session.commit()

        keys = self.session.scalars(select(Objekt.object_key)).all()
        self.assertEqual(keys.count("readme.txt"), 2)

    def test_version_id_must_be_unique(self):
        self.session.add(self._objekt(object_key="a.txt", version_id="a" * 32))
        self.session.commit()

        self.session.add(
            self._objekt(object_key="b.txt", version_id="a" * 32),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_root_may_upload_to_foreign_bucket(self):
        root = User(username="root", is_root=True)
        self.session.add(root)
        self.session.commit()
        self.session.refresh(root)

        objekt = self._objekt(
            user_id=root.id,
            object_key="from-root.txt",
            etag="c" * 32,
        )
        self.session.add(objekt)
        self.session.commit()
        self.session.refresh(objekt)

        self.assertEqual(objekt.bucket_id, self.bucket.id)
        self.assertEqual(objekt.user_id, root.id)
        self.assertNotEqual(objekt.user_id, self.bucket.user_id)

    def test_delete_marker_has_no_payload(self):
        objekt = self._delete_marker(object_key="gone.txt")
        self.session.add(objekt)
        self.session.commit()
        self.session.refresh(objekt)

        self.assertTrue(objekt.delete_marker)
        self.assertIsNone(objekt.size_bytes)
        self.assertIsNone(objekt.etag)
        self.assertIsNone(objekt.content_type)
        self.assertIsNone(objekt.lock_mode)
        self.assertIsNone(objekt.retain_until)
        self.assertFalse(objekt.legal_hold)

    def test_object_lock_fields(self):
        objekt = self._objekt(
            lock_mode="COMPLIANCE",
            retain_until=1_704_067_200,
            legal_hold=True,
        )
        self.session.add(objekt)
        self.session.commit()
        self.session.refresh(objekt)

        self.assertFalse(objekt.delete_marker)
        self.assertEqual(objekt.lock_mode, "COMPLIANCE")
        self.assertEqual(objekt.retain_until, 1_704_067_200)
        self.assertTrue(objekt.legal_hold)

    def test_payload_required_when_not_delete_marker(self):
        self._assert_rejects(self._objekt(etag=None))

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
        self._assert_rejects(self._objekt(lock_mode="GOVERNANCE"))

    def test_lock_mode_must_be_governance_or_compliance(self):
        self._assert_rejects(
            self._objekt(
                lock_mode="INVALID",
                retain_until=1_704_067_200,
            ),
        )

    def test_size_bytes_must_be_nonnegative(self):
        self._assert_rejects(self._objekt(size_bytes=-1))

    def test_relationship_back_to_bucket(self):
        objekt = self._objekt(object_key="x.bin", size_bytes=0, etag="c" * 32)
        self.session.add(objekt)
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt)
            .where(Objekt.id == objekt.id)
            .options(selectinload(Objekt.object_bucket)),
        )

        self.assertEqual(loaded.object_bucket.id, self.bucket.id)
        self.assertEqual(loaded.object_bucket.bucket_name, "photos")

    def test_relationship_back_to_user(self):
        objekt = self._objekt(object_key="x.bin", size_bytes=0, etag="c" * 32)
        self.session.add(objekt)
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt)
            .where(Objekt.id == objekt.id)
            .options(selectinload(Objekt.object_user)),
        )

        self.assertEqual(loaded.object_user.id, self.user.id)
        self.assertEqual(loaded.object_user.username, "alice")

    def test_bucket_relationship_to_objekts(self):
        self.session.add(self._objekt(object_key="a.txt", etag="a" * 32))
        self.session.add(
            self._objekt(object_key="b.txt", size_bytes=2, etag="b" * 32),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket)
            .where(Bucket.id == self.bucket.id)
            .options(selectinload(Bucket.bucket_objects)),
        )

        keys = sorted(o.object_key for o in loaded.bucket_objects)
        self.assertEqual(keys, ["a.txt", "b.txt"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._objekt())
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket).where(Bucket.id == self.bucket.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.bucket_objects

    def test_object_bucket_access_without_eager_load_raises(self):
        objekt = self._objekt()
        self.session.add(objekt)
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt).where(Objekt.id == objekt.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_bucket

    def test_object_user_access_without_eager_load_raises(self):
        objekt = self._objekt()
        self.session.add(objekt)
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt).where(Objekt.id == objekt.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_user

    def test_bucket_delete_is_restricted(self):
        self.session.add(self._objekt())
        self.session.commit()

        self.session.delete(self.bucket)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_uploader_delete_is_restricted(self):
        root = User(username="root", is_root=True)
        self.session.add(root)
        self.session.commit()
        self.session.refresh(root)

        self.session.add(
            self._objekt(user_id=root.id, object_key="root.txt"),
        )
        self.session.commit()

        self.session.delete(root)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_user_delete_is_restricted(self):
        self.session.add(self._objekt())
        self.session.commit()

        self.session.delete(self.user)
        with self.assertRaises(IntegrityError):
            self.session.commit()
