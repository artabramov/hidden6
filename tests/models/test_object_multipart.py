# tests/models/test_object_multipart.py
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
from app.models.object_multipart import ObjectMultipart  # noqa: E402
from app.models.object_multipart_metadata import ObjectMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_tag import ObjectMultipartTag  # noqa: E402, F401
from app.models.object_multipart_part import ObjectMultipartPart  # noqa: E402, F401
from app.models.object_version import ObjectVersion  # noqa: E402, F401
from app.models.object_version_metadata import ObjectVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import ObjectVersionTag  # noqa: E402, F401
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.object_metadata import ObjectMetadata  # noqa: E402, F401
from app.models.object_tag import ObjectTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestMultipartModel(unittest.TestCase):

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

    def _multipart(self, **kwargs) -> ObjectMultipart:
        defaults = {
            "bucket_id": self.bucket.id,
            "user_id": self.user.id,
            "upload_id": "a" * 32,
            "object_key": "a.txt",
        }
        defaults.update(kwargs)
        return ObjectMultipart(**defaults)

    def test_tablename(self):
        self.assertEqual(
            ObjectMultipart.__tablename__,
            "objects_multiparts",
        )

    def test_persists_required_fields_and_defaults(self):
        multipart = self._multipart(object_key="album/a.jpg")
        self.session.add(multipart)
        self.session.commit()
        self.session.refresh(multipart)

        self.assertIsNotNone(multipart.id)
        self.assertEqual(multipart.bucket_id, self.bucket.id)
        self.assertEqual(multipart.user_id, self.user.id)
        self.assertEqual(multipart.upload_id, "a" * 32)
        self.assertEqual(multipart.object_key, "album/a.jpg")
        self.assertEqual(multipart.content_type, "application/octet-stream")
        self.assertIsInstance(multipart.created_at, int)

    def test_upload_id_is_unique(self):
        self.session.add(self._multipart())
        self.session.commit()

        self.session.add(self._multipart(object_key="other.txt"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_key_allowed_for_parallel_uploads(self):
        self.session.add(self._multipart(upload_id="a" * 32))
        self.session.add(self._multipart(upload_id="b" * 32))
        self.session.commit()

        keys = self.session.scalars(select(ObjectMultipart.object_key)).all()
        self.assertEqual(keys.count("a.txt"), 2)

    def test_root_may_upload_to_foreign_bucket(self):
        root = User(username="root", is_root=True)
        self.session.add(root)
        self.session.commit()
        self.session.refresh(root)

        multipart = self._multipart(user_id=root.id)
        self.session.add(multipart)
        self.session.commit()
        self.session.refresh(multipart)

        self.assertEqual(multipart.bucket_id, self.bucket.id)
        self.assertNotEqual(multipart.user_id, self.bucket.user_id)

    def test_relationship_back_to_bucket(self):
        multipart = self._multipart()
        self.session.add(multipart)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectMultipart)
            .where(ObjectMultipart.id == multipart.id)
            .options(selectinload(ObjectMultipart.object_multipart_bucket)),
        )

        self.assertEqual(loaded.object_multipart_bucket.id, self.bucket.id)

    def test_relationship_back_to_user(self):
        multipart = self._multipart()
        self.session.add(multipart)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectMultipart)
            .where(ObjectMultipart.id == multipart.id)
            .options(selectinload(ObjectMultipart.object_multipart_user)),
        )

        self.assertEqual(loaded.object_multipart_user.username, "alice")

    def test_bucket_relationship_to_multiparts(self):
        self.session.add(self._multipart(upload_id="a" * 32))
        self.session.add(
            self._multipart(upload_id="b" * 32, object_key="b.txt"),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket)
            .where(Bucket.id == self.bucket.id)
            .options(selectinload(Bucket.bucket_objects_multiparts)),
        )

        keys = sorted(m.object_key for m in loaded.bucket_objects_multiparts)
        self.assertEqual(keys, ["a.txt", "b.txt"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._multipart())
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket).where(Bucket.id == self.bucket.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.bucket_objects_multiparts

    def test_multipart_bucket_access_without_eager_load_raises(self):
        multipart = self._multipart()
        self.session.add(multipart)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectMultipart).where(ObjectMultipart.id == multipart.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_multipart_bucket

    def test_multipart_user_access_without_eager_load_raises(self):
        multipart = self._multipart()
        self.session.add(multipart)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectMultipart).where(ObjectMultipart.id == multipart.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_multipart_user

    def test_bucket_delete_is_restricted(self):
        self.session.add(self._multipart())
        self.session.commit()

        self.session.delete(self.bucket)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_user_delete_is_restricted(self):
        self.session.add(self._multipart())
        self.session.commit()

        self.session.delete(self.user)
        with self.assertRaises(IntegrityError):
            self.session.commit()
