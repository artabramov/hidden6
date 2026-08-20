# tests/models/test_object.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.bucket import S3Bucket  # noqa: E402
from app.models.bucket_tag import S3BucketTag  # noqa: E402, F401
from app.models.object import S3Object  # noqa: E402
from app.models.object_metadata import S3ObjectMetadata  # noqa: E402, F401
from app.models.object_multipart import S3ObjectMultipart  # noqa: E402, F401
from app.models.object_multipart_metadata import S3ObjectMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_tag import S3ObjectMultipartTag  # noqa: E402, F401
from app.models.object_multipart_part import S3ObjectMultipartPart  # noqa: E402, F401
from app.models.object_tag import S3ObjectTag  # noqa: E402, F401
from app.models.object_version import S3ObjectVersion  # noqa: E402, F401
from app.models.object_version_metadata import S3ObjectVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import S3ObjectVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjectModel(unittest.TestCase):

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

        self.bucket = S3Bucket(
            user_id=self.user.id,
            bucket_name="photos",
        )
        self.session.add(self.bucket)
        self.session.commit()
        self.session.refresh(self.bucket)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _object(self, **kwargs) -> S3Object:
        defaults = {
            "bucket_id": self.bucket.id,
            "user_id": self.user.id,
            "object_key": "a.txt",
            "size_bytes": 1,
            "etag": "a" * 32,
            "content_type": "text/plain",
        }
        defaults.update(kwargs)
        return S3Object(**defaults)

    def _delete_marker(self, **kwargs) -> S3Object:
        defaults = {
            "delete_marker": True,
            "size_bytes": None,
            "etag": None,
            "content_type": None,
        }
        defaults.update(kwargs)
        return self._object(**defaults)

    def _assert_rejects(self, s3_object):
        self.session.add(s3_object)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_tablename(self):
        self.assertEqual(S3Object.__tablename__, "objects")

    def test_persists_required_fields_and_defaults(self):
        s3_object = self._object(
            object_key="album/a.jpg",
            size_bytes=1024,
            etag="d41d8cd98f00b204e9800998ecf8427e",
            content_type="image/jpeg",
        )
        self.session.add(s3_object)
        self.session.commit()
        self.session.refresh(s3_object)

        self.assertIsNotNone(s3_object.id)
        self.assertEqual(s3_object.bucket_id, self.bucket.id)
        self.assertEqual(s3_object.user_id, self.user.id)
        self.assertEqual(s3_object.object_key, "album/a.jpg")
        self.assertEqual(s3_object.size_bytes, 1024)
        self.assertEqual(s3_object.etag, "d41d8cd98f00b204e9800998ecf8427e")
        self.assertEqual(s3_object.content_type, "image/jpeg")
        self.assertIsNone(s3_object.version_uuid)
        self.assertFalse(s3_object.delete_marker)
        self.assertIsNone(s3_object.lock_mode)
        self.assertIsNone(s3_object.retain_until)
        self.assertFalse(s3_object.legal_hold)
        self.assertIsInstance(s3_object.created_at, int)
        self.assertIsInstance(s3_object.modified_at, int)

    def test_object_key_unique_per_bucket(self):
        self.session.add(self._object(object_key="same.txt", etag="a" * 32))
        self.session.commit()

        self.session.add(
            self._object(
                object_key="same.txt",
                size_bytes=2,
                etag="b" * 32,
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_key_allowed_in_different_buckets(self):
        other = S3Bucket(user_id=self.user.id, bucket_name="docs")
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(self._object(object_key="readme.txt", etag="a" * 32))
        self.session.add(
            self._object(
                bucket_id=other.id,
                object_key="readme.txt",
                size_bytes=2,
                etag="b" * 32,
            ),
        )
        self.session.commit()

        keys = self.session.scalars(select(S3Object.object_key)).all()
        self.assertEqual(keys.count("readme.txt"), 2)

    def test_version_uuid_must_be_unique(self):
        self.session.add(self._object(object_key="a.txt", version_uuid="a" * 32))
        self.session.commit()

        self.session.add(
            self._object(object_key="b.txt", version_uuid="a" * 32),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_root_may_upload_to_foreign_bucket(self):
        root = User(username="root", is_root=True)
        self.session.add(root)
        self.session.commit()
        self.session.refresh(root)

        s3_object = self._object(
            user_id=root.id,
            object_key="from-root.txt",
            etag="c" * 32,
        )
        self.session.add(s3_object)
        self.session.commit()
        self.session.refresh(s3_object)

        self.assertEqual(s3_object.bucket_id, self.bucket.id)
        self.assertEqual(s3_object.user_id, root.id)
        self.assertNotEqual(s3_object.user_id, self.bucket.user_id)

    def test_delete_marker_has_no_payload(self):
        s3_object = self._delete_marker(object_key="gone.txt")
        self.session.add(s3_object)
        self.session.commit()
        self.session.refresh(s3_object)

        self.assertTrue(s3_object.delete_marker)
        self.assertIsNone(s3_object.size_bytes)
        self.assertIsNone(s3_object.etag)
        self.assertIsNone(s3_object.content_type)
        self.assertIsNone(s3_object.lock_mode)
        self.assertIsNone(s3_object.retain_until)
        self.assertFalse(s3_object.legal_hold)

    def test_object_lock_fields(self):
        s3_object = self._object(
            lock_mode="COMPLIANCE",
            retain_until=1_704_067_200,
            legal_hold=True,
        )
        self.session.add(s3_object)
        self.session.commit()
        self.session.refresh(s3_object)

        self.assertFalse(s3_object.delete_marker)
        self.assertEqual(s3_object.lock_mode, "COMPLIANCE")
        self.assertEqual(s3_object.retain_until, 1_704_067_200)
        self.assertTrue(s3_object.legal_hold)

    def test_payload_required_when_not_delete_marker(self):
        self._assert_rejects(self._object(etag=None))

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
        self._assert_rejects(self._object(lock_mode="GOVERNANCE"))

    def test_lock_mode_must_be_governance_or_compliance(self):
        self._assert_rejects(
            self._object(
                lock_mode="INVALID",
                retain_until=1_704_067_200,
            ),
        )

    def test_size_bytes_must_be_nonnegative(self):
        self._assert_rejects(self._object(size_bytes=-1))

    def test_relationship_back_to_bucket(self):
        s3_object = self._object(object_key="x.bin", size_bytes=0, etag="c" * 32)
        self.session.add(s3_object)
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Object)
            .where(S3Object.id == s3_object.id)
            .options(selectinload(S3Object.object_bucket)),
        )

        self.assertEqual(loaded.object_bucket.id, self.bucket.id)
        self.assertEqual(loaded.object_bucket.bucket_name, "photos")

    def test_relationship_back_to_user(self):
        s3_object = self._object(object_key="x.bin", size_bytes=0, etag="c" * 32)
        self.session.add(s3_object)
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Object)
            .where(S3Object.id == s3_object.id)
            .options(selectinload(S3Object.object_user)),
        )

        self.assertEqual(loaded.object_user.id, self.user.id)
        self.assertEqual(loaded.object_user.username, "alice")

    def test_bucket_relationship_to_objects(self):
        self.session.add(self._object(object_key="a.txt", etag="a" * 32))
        self.session.add(
            self._object(object_key="b.txt", size_bytes=2, etag="b" * 32),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Bucket)
            .where(S3Bucket.id == self.bucket.id)
            .options(selectinload(S3Bucket.bucket_objects)),
        )

        keys = sorted(o.object_key for o in loaded.bucket_objects)
        self.assertEqual(keys, ["a.txt", "b.txt"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._object())
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Bucket).where(S3Bucket.id == self.bucket.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.bucket_objects

    def test_object_bucket_access_without_eager_load_raises(self):
        s3_object = self._object()
        self.session.add(s3_object)
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Object).where(S3Object.id == s3_object.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_bucket

    def test_object_user_access_without_eager_load_raises(self):
        s3_object = self._object()
        self.session.add(s3_object)
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Object).where(S3Object.id == s3_object.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_user

    def test_bucket_delete_is_restricted(self):
        self.session.add(self._object())
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
            self._object(user_id=root.id, object_key="root.txt"),
        )
        self.session.commit()

        self.session.delete(root)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_user_delete_is_restricted(self):
        self.session.add(self._object())
        self.session.commit()

        self.session.delete(self.user)
        with self.assertRaises(IntegrityError):
            self.session.commit()
