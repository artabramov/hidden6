# tests/models/test_object_tag.py
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
from app.models.object import Objekt  # noqa: E402
from app.models.object_metadata import ObjectMetadata  # noqa: E402, F401
from app.models.object_multipart import ObjectMultipart  # noqa: E402, F401
from app.models.object_multipart_metadata import ObjectMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_tag import ObjectMultipartTag  # noqa: E402, F401
from app.models.object_multipart_part import ObjectMultipartPart  # noqa: E402, F401
from app.models.object_tag import ObjectTag  # noqa: E402
from app.models.object_version import ObjectVersion  # noqa: E402, F401
from app.models.object_version_metadata import ObjectVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import ObjectVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjectTagModel(unittest.TestCase):

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

    def _tag(self, **kwargs) -> ObjectTag:
        defaults = {
            "object_id": self.objekt.id,
            "tag_key": "color",
            "tag_value": "red",
        }
        defaults.update(kwargs)
        return ObjectTag(**defaults)

    def test_tablename(self):
        self.assertEqual(ObjectTag.__tablename__, "objects_tags")

    def test_persists_required_fields(self):
        row = self._tag(tag_key="owner", tag_value="alice")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertIsNotNone(row.id)
        self.assertEqual(row.object_id, self.objekt.id)
        self.assertEqual(row.tag_key, "owner")
        self.assertEqual(row.tag_value, "alice")

    def test_empty_tag_value_is_allowed(self):
        row = self._tag(tag_key="blank", tag_value="")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.tag_value, "")

    def test_tag_key_unique_per_objekt(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.commit()

        self.session.add(self._tag(tag_key="color", tag_value="blue"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_tag_key_allowed_on_different_objekts(self):
        other = Objekt(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            object_key="b.txt",
            size_bytes=2,
            etag="d" * 32,
            content_type="text/plain",
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(
            self._tag(
                object_id=other.id,
                tag_key="color",
                tag_value="blue",
            ),
        )
        self.session.commit()

        rows = self.session.scalars(select(ObjectTag)).all()
        self.assertEqual(len(rows), 2)

    def test_relationship_back_to_objekt(self):
        row = self._tag()
        self.session.add(row)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectTag)
            .where(ObjectTag.id == row.id)
            .options(selectinload(ObjectTag.object_tag_object)),
        )

        self.assertEqual(loaded.object_tag_object.id, self.objekt.id)
        self.assertEqual(loaded.object_tag_object.object_key, "a.txt")

    def test_object_relationship_to_tags(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(self._tag(tag_key="owner", tag_value="alice"))
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt)
            .where(Objekt.id == self.objekt.id)
            .options(selectinload(Objekt.object_tags)),
        )

        keys = sorted(item.tag_key for item in loaded.object_tags)
        self.assertEqual(keys, ["color", "owner"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._tag())
        self.session.commit()

        loaded = self.session.scalar(
            select(Objekt).where(Objekt.id == self.objekt.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_tags

    def test_cascade_delete_with_objekt(self):
        self.session.add(self._tag())
        self.session.commit()

        self.session.delete(self.objekt)
        self.session.commit()

        remaining = self.session.scalars(select(ObjectTag)).all()
        self.assertEqual(remaining, [])
