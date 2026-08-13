# tests/models/test_objekt_multipart_metadata.py
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
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.objekt_metadata import ObjektMetadata  # noqa: E402, F401
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.objekt_multipart_metadata import ObjektMultipartMetadata  # noqa: E402
from app.models.objekt_multipart_tag import ObjektMultipartTag  # noqa: E402, F401
from app.models.objekt_multipart_part import ObjektMultipartPart  # noqa: E402, F401
from app.models.objekt_tag import ObjektTag  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
from app.models.objekt_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
from app.models.objekt_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjektMultipartMetadataModel(unittest.TestCase):

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

        self.multipart = ObjektMultipart(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            upload_id="a" * 32,
            object_key="a.txt",
        )
        self.session.add(self.multipart)
        self.session.commit()
        self.session.refresh(self.multipart)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def _metadata(self, **kwargs) -> ObjektMultipartMetadata:
        defaults = {
            "objekt_multipart_id": self.multipart.id,
            "meta_key": "x-amz-meta-color",
            "meta_value": "red",
        }
        defaults.update(kwargs)
        return ObjektMultipartMetadata(**defaults)

    def test_tablename(self):
        self.assertEqual(
            ObjektMultipartMetadata.__tablename__,
            "objekts_multiparts_metadata",
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
        self.assertEqual(row.objekt_multipart_id, self.multipart.id)
        self.assertEqual(row.meta_key, "x-amz-meta-owner")
        self.assertEqual(row.meta_value, "alice")

    def test_meta_key_unique_per_multipart(self):
        self.session.add(
            self._metadata(meta_key="x-amz-meta-color", meta_value="red"),
        )
        self.session.commit()

        self.session.add(
            self._metadata(
                meta_key="x-amz-meta-color",
                meta_value="blue",
            ),
        )
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_meta_key_allowed_on_different_multiparts(self):
        other = ObjektMultipart(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            upload_id="b" * 32,
            object_key="b.txt",
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(
            self._metadata(meta_key="x-amz-meta-color", meta_value="red"),
        )
        self.session.add(
            self._metadata(
                objekt_multipart_id=other.id,
                meta_key="x-amz-meta-color",
                meta_value="blue",
            ),
        )
        self.session.commit()

        rows = self.session.scalars(select(ObjektMultipartMetadata)).all()
        self.assertEqual(len(rows), 2)

    def test_relationship_back_to_multipart(self):
        row = self._metadata()
        self.session.add(row)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipartMetadata)
            .where(ObjektMultipartMetadata.id == row.id)
            .options(
                selectinload(
                    ObjektMultipartMetadata.objekt_multipart_metadata_objekt_multipart,
                ),
            ),
        )

        self.assertEqual(
            loaded.objekt_multipart_metadata_objekt_multipart.id,
            self.multipart.id,
        )
        self.assertEqual(
            loaded.objekt_multipart_metadata_objekt_multipart.upload_id,
            "a" * 32,
        )

    def test_multipart_relationship_to_metadata(self):
        self.session.add(
            self._metadata(meta_key="x-amz-meta-color", meta_value="red"),
        )
        self.session.add(
            self._metadata(meta_key="Cache-Control", meta_value="no-cache"),
        )
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipart)
            .where(ObjektMultipart.id == self.multipart.id)
            .options(selectinload(ObjektMultipart.objekt_multipart_metadata)),
        )

        keys = sorted(
            item.meta_key for item in loaded.objekt_multipart_metadata
        )
        self.assertEqual(keys, ["Cache-Control", "x-amz-meta-color"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._metadata())
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipart).where(
                ObjektMultipart.id == self.multipart.id,
            ),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.objekt_multipart_metadata

    def test_cascade_delete_with_multipart(self):
        self.session.add(self._metadata())
        self.session.commit()

        self.session.delete(self.multipart)
        self.session.commit()

        remaining = self.session.scalars(select(ObjektMultipartMetadata)).all()
        self.assertEqual(remaining, [])
