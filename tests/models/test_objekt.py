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
from app.models.objekt import Objekt  # noqa: E402
from app.models.objekt_metadata import ObjektMetadata  # noqa: E402, F401
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402, F401
from app.models.objekt_multipart_metadata import ObjektMultipartMetadata  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
from app.models.objekt_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
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
        }
        defaults.update(kwargs)
        return Objekt(**defaults)

    def test_tablename(self):
        self.assertEqual(Objekt.__tablename__, "objekts")

    def test_persists_required_fields_and_defaults(self):
        objekt = self._objekt(
            object_key="album/a.jpg",
            size_bytes=1024,
            etag="d41d8cd98f00b204e9800998ecf8427e",
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
        self.assertEqual(objekt.content_type, "application/octet-stream")
        self.assertIsInstance(objekt.created_at, int)
        self.assertIsNone(objekt.updated_at)

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

    def test_relationship_back_to_bucket(self):
        objekt = self._objekt(object_key="x.bin", size_bytes=0, etag="c" * 32)
        self.session.add(objekt)
        self.session.commit()
        self.session.refresh(objekt)

        self.assertEqual(objekt.objekt_bucket.id, self.bucket.id)
        self.assertEqual(objekt.objekt_bucket.bucket_name, "photos")

    def test_relationship_back_to_user(self):
        objekt = self._objekt(object_key="x.bin", size_bytes=0, etag="c" * 32)
        self.session.add(objekt)
        self.session.commit()
        self.session.refresh(objekt)

        self.assertEqual(objekt.objekt_user.id, self.user.id)
        self.assertEqual(objekt.objekt_user.username, "alice")

    def test_bucket_relationship_to_objekts(self):
        self.session.add(self._objekt(object_key="a.txt", etag="a" * 32))
        self.session.add(
            self._objekt(object_key="b.txt", size_bytes=2, etag="b" * 32),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket)
            .where(Bucket.id == self.bucket.id)
            .options(selectinload(Bucket.bucket_objekts)),
        )

        keys = sorted(o.object_key for o in loaded.bucket_objekts)
        self.assertEqual(keys, ["a.txt", "b.txt"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._objekt())
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket).where(Bucket.id == self.bucket.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.bucket_objekts

    def test_cascade_delete_with_bucket(self):
        self.session.add(self._objekt())
        self.session.commit()

        self.session.delete(self.bucket)
        self.session.commit()

        remaining = self.session.scalars(select(Objekt)).all()
        self.assertEqual(remaining, [])

    def test_cascade_delete_with_uploader(self):
        root = User(username="root", is_root=True)
        self.session.add(root)
        self.session.commit()
        self.session.refresh(root)

        self.session.add(
            self._objekt(user_id=root.id, object_key="root.txt"),
        )
        self.session.commit()

        self.session.delete(root)
        self.session.commit()

        remaining = self.session.scalars(select(Objekt)).all()
        self.assertEqual(remaining, [])
        self.assertIsNotNone(
            self.session.scalar(
                select(Bucket).where(Bucket.id == self.bucket.id),
            ),
        )

    def test_cascade_delete_with_user(self):
        self.session.add(self._objekt())
        self.session.commit()

        self.session.delete(self.user)
        self.session.commit()

        remaining = self.session.scalars(select(Objekt)).all()
        self.assertEqual(remaining, [])
