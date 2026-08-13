# tests/models/test_bucket_tag.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.bucket_tag import BucketTag  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.objekt_metadata import ObjektMetadata  # noqa: E402, F401
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402, F401
from app.models.objekt_multipart_metadata import ObjektMultipartMetadata  # noqa: E402, F401
from app.models.objekt_multipart_tag import ObjektMultipartTag  # noqa: E402, F401
from app.models.objekt_tag import ObjektTag  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
from app.models.objekt_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
from app.models.objekt_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestBucketTagModel(unittest.TestCase):

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

    def _tag(self, **kwargs) -> BucketTag:
        defaults = {
            "bucket_id": self.bucket.id,
            "tag_key": "color",
            "tag_value": "red",
        }
        defaults.update(kwargs)
        return BucketTag(**defaults)

    def test_tablename(self):
        self.assertEqual(BucketTag.__tablename__, "buckets_tags")

    def test_persists_required_fields(self):
        row = self._tag(tag_key="owner", tag_value="alice")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertIsNotNone(row.id)
        self.assertEqual(row.bucket_id, self.bucket.id)
        self.assertEqual(row.tag_key, "owner")
        self.assertEqual(row.tag_value, "alice")

    def test_empty_tag_value_is_allowed(self):
        row = self._tag(tag_key="blank", tag_value="")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.tag_value, "")

    def test_tag_key_unique_per_bucket(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.commit()

        self.session.add(self._tag(tag_key="color", tag_value="blue"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_tag_key_allowed_on_different_buckets(self):
        other = Bucket(
            user_id=self.user.id,
            bucket_name="docs",
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(
            self._tag(
                bucket_id=other.id,
                tag_key="color",
                tag_value="blue",
            ),
        )
        self.session.commit()

        rows = self.session.scalars(select(BucketTag)).all()
        self.assertEqual(len(rows), 2)

    def test_relationship_back_to_bucket(self):
        row = self._tag()
        self.session.add(row)
        self.session.commit()

        loaded = self.session.scalar(
            select(BucketTag)
            .where(BucketTag.id == row.id)
            .options(selectinload(BucketTag.bucket_tag_bucket)),
        )

        self.assertEqual(loaded.bucket_tag_bucket.id, self.bucket.id)
        self.assertEqual(loaded.bucket_tag_bucket.bucket_name, "photos")

    def test_bucket_relationship_to_tags(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(self._tag(tag_key="owner", tag_value="alice"))
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket)
            .where(Bucket.id == self.bucket.id)
            .options(selectinload(Bucket.bucket_tags)),
        )

        keys = sorted(item.tag_key for item in loaded.bucket_tags)
        self.assertEqual(keys, ["color", "owner"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._tag())
        self.session.commit()

        loaded = self.session.scalar(
            select(Bucket).where(Bucket.id == self.bucket.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.bucket_tags

    def test_cascade_delete_with_bucket(self):
        self.session.add(self._tag())
        self.session.commit()

        self.session.delete(self.bucket)
        self.session.commit()

        remaining = self.session.scalars(select(BucketTag)).all()
        self.assertEqual(remaining, [])
