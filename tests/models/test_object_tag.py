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
from app.models.object import S3Object  # noqa: E402
from app.models.object_metadata import S3ObjectMetadata  # noqa: E402, F401
from app.models.object_multipart import S3ObjectMultipart  # noqa: E402, F401
from app.models.object_multipart_metadata import S3S3ObjectMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_tag import S3S3ObjectMultipartTag  # noqa: E402, F401
from app.models.object_multipart_part import S3S3ObjectMultipartPart  # noqa: E402, F401
from app.models.object_tag import S3ObjectTag  # noqa: E402
from app.models.object_version import S3ObjectVersion  # noqa: E402, F401
from app.models.object_version_metadata import S3S3ObjectVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import S3S3ObjectVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestS3ObjectTagModel(unittest.TestCase):

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

        self.s3_object = S3Object(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            object_key="a.txt",
            size_bytes=10,
            etag="c" * 32,
            content_type="text/plain",
        )
        self.session.add(self.s3_object)
        self.session.commit()
        self.session.refresh(self.s3_object)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _tag(self, **kwargs) -> S3ObjectTag:
        defaults = {
            "object_id": self.s3_object.id,
            "tag_key": "color",
            "tag_value": "red",
        }
        defaults.update(kwargs)
        return S3ObjectTag(**defaults)

    def test_tablename(self):
        self.assertEqual(S3ObjectTag.__tablename__, "objects_tags")

    def test_persists_required_fields(self):
        row = self._tag(tag_key="owner", tag_value="alice")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertIsNotNone(row.id)
        self.assertEqual(row.object_id, self.s3_object.id)
        self.assertEqual(row.tag_key, "owner")
        self.assertEqual(row.tag_value, "alice")

    def test_empty_tag_value_is_allowed(self):
        row = self._tag(tag_key="blank", tag_value="")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.tag_value, "")

    def test_tag_key_unique_per_object(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.commit()

        self.session.add(self._tag(tag_key="color", tag_value="blue"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_tag_key_allowed_on_different_objects(self):
        other = S3Object(
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

        rows = self.session.scalars(select(S3ObjectTag)).all()
        self.assertEqual(len(rows), 2)

    def test_relationship_back_to_object(self):
        row = self._tag()
        self.session.add(row)
        self.session.commit()

        loaded = self.session.scalar(
            select(S3ObjectTag)
            .where(S3ObjectTag.id == row.id)
            .options(selectinload(S3ObjectTag.object_tag_object)),
        )

        self.assertEqual(loaded.object_tag_object.id, self.s3_object.id)
        self.assertEqual(loaded.object_tag_object.object_key, "a.txt")

    def test_object_relationship_to_tags(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(self._tag(tag_key="owner", tag_value="alice"))
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Object)
            .where(S3Object.id == self.s3_object.id)
            .options(selectinload(S3Object.object_tags)),
        )

        keys = sorted(item.tag_key for item in loaded.object_tags)
        self.assertEqual(keys, ["color", "owner"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._tag())
        self.session.commit()

        loaded = self.session.scalar(
            select(S3Object).where(S3Object.id == self.s3_object.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_tags

    def test_cascade_delete_with_object(self):
        self.session.add(self._tag())
        self.session.commit()

        self.session.delete(self.s3_object)
        self.session.commit()

        remaining = self.session.scalars(select(S3ObjectTag)).all()
        self.assertEqual(remaining, [])
