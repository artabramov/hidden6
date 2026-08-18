# tests/models/test_object_version_metadata.py
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
from app.models.object_metadata import ObjectMetadata  # noqa: E402, F401
from app.models.object_multipart import ObjectMultipart  # noqa: E402, F401
from app.models.object_multipart_metadata import ObjectMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_tag import ObjectMultipartTag  # noqa: E402, F401
from app.models.object_multipart_part import ObjectMultipartPart  # noqa: E402, F401
from app.models.object_tag import ObjectTag  # noqa: E402, F401
from app.models.object_version import ObjectVersion  # noqa: E402
from app.models.object_version_metadata import ObjectVersionMetadata  # noqa: E402
from app.models.object_version_tag import ObjectVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjectVersionMetadataModel(unittest.TestCase):

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

        self.objekt = S3Object(
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

        self.version = ObjectVersion(
            object_id=self.objekt.id,
            user_id=self.user.id,
            version_id="a" * 32,
            modified_at=1_704_067_200,
            size_bytes=1,
            etag="b" * 32,
            content_type="text/plain",
        )
        self.session.add(self.version)
        self.session.commit()
        self.session.refresh(self.version)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _metadata(self, **kwargs) -> ObjectVersionMetadata:
        defaults = {
            "object_version_id": self.version.id,
            "meta_key": "x-amz-meta-color",
            "meta_value": "red",
        }
        defaults.update(kwargs)
        return ObjectVersionMetadata(**defaults)

    def test_tablename(self):
        self.assertEqual(
            ObjectVersionMetadata.__tablename__,
            "objects_versions_metadata",
        )

    def test_persists_required_fields(self):
        row = self._metadata(
            meta_key="x-amz-meta-owner",
            meta_value="alice",
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertIsNotNone(row.id)
        self.assertEqual(row.object_version_id, self.version.id)
        self.assertEqual(row.meta_key, "x-amz-meta-owner")
        self.assertEqual(row.meta_value, "alice")

    def test_meta_key_unique_per_version(self):
        self.session.add(
            self._metadata(meta_key="x-amz-meta-color", meta_value="red"),
        )
        self.session.commit()

        self.session.add(
            self._metadata(meta_key="x-amz-meta-color", meta_value="blue"),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_meta_key_allowed_on_different_versions(self):
        other = ObjectVersion(
            object_id=self.objekt.id,
            user_id=self.user.id,
            version_id="b" * 32,
            modified_at=1_704_067_200,
            size_bytes=2,
            etag="c" * 32,
            content_type="text/plain",
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(
            self._metadata(meta_key="x-amz-meta-color", meta_value="red"),
        )
        self.session.add(
            self._metadata(
                object_version_id=other.id,
                meta_key="x-amz-meta-color",
                meta_value="blue",
            ),
        )
        self.session.commit()

        rows = self.session.scalars(select(ObjectVersionMetadata)).all()
        self.assertEqual(len(rows), 2)

    def test_relationship_back_to_version(self):
        row = self._metadata()
        self.session.add(row)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectVersionMetadata)
            .where(ObjectVersionMetadata.id == row.id)
            .options(
                selectinload(
                    ObjectVersionMetadata.object_version_metadata_object_version,
                ),
            ),
        )

        self.assertEqual(
            loaded.object_version_metadata_object_version.id,
            self.version.id,
        )
        self.assertEqual(
            loaded.object_version_metadata_object_version.version_id,
            "a" * 32,
        )

    def test_version_relationship_to_metadata(self):
        self.session.add(
            self._metadata(meta_key="x-amz-meta-color", meta_value="red"),
        )
        self.session.add(
            self._metadata(meta_key="Cache-Control", meta_value="no-cache"),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectVersion)
            .where(ObjectVersion.id == self.version.id)
            .options(selectinload(ObjectVersion.object_version_metadata)),
        )

        keys = sorted(item.meta_key for item in loaded.object_version_metadata)
        self.assertEqual(keys, ["Cache-Control", "x-amz-meta-color"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._metadata())
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjectVersion).where(ObjectVersion.id == self.version.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.object_version_metadata

    def test_cascade_delete_with_version(self):
        self.session.add(self._metadata())
        self.session.commit()

        self.session.delete(self.version)
        self.session.commit()

        remaining = self.session.scalars(select(ObjectVersionMetadata)).all()
        self.assertEqual(remaining, [])
