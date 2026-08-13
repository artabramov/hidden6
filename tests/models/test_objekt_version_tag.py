# tests/models/test_objekt_version_tag.py
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
from app.models.objekt_tag import ObjektTag  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402
from app.models.objekt_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
from app.models.objekt_version_tag import ObjektVersionTag  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjektVersionTagModel(unittest.TestCase):

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

        self.version = ObjektVersion(
            objekt_id=self.objekt.id,
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

    def _tag(self, **kwargs) -> ObjektVersionTag:
        defaults = {
            "objekt_version_id": self.version.id,
            "tag_key": "color",
            "tag_value": "red",
        }
        defaults.update(kwargs)
        return ObjektVersionTag(**defaults)

    def test_tablename(self):
        self.assertEqual(
            ObjektVersionTag.__tablename__,
            "objekts_versions_tags",
        )

    def test_persists_required_fields(self):
        row = self._tag(tag_key="owner", tag_value="alice")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertIsNotNone(row.id)
        self.assertEqual(row.objekt_version_id, self.version.id)
        self.assertEqual(row.tag_key, "owner")
        self.assertEqual(row.tag_value, "alice")

    def test_empty_tag_value_is_allowed(self):
        row = self._tag(tag_key="blank", tag_value="")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.tag_value, "")

    def test_tag_key_unique_per_version(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.commit()

        self.session.add(self._tag(tag_key="color", tag_value="blue"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_tag_key_allowed_on_different_versions(self):
        other = ObjektVersion(
            objekt_id=self.objekt.id,
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

        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(
            self._tag(
                objekt_version_id=other.id,
                tag_key="color",
                tag_value="blue",
            ),
        )
        self.session.commit()

        rows = self.session.scalars(select(ObjektVersionTag)).all()
        self.assertEqual(len(rows), 2)

    def test_relationship_back_to_version(self):
        row = self._tag()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(
            row.objekt_version_tag_objekt_version.id,
            self.version.id,
        )
        self.assertEqual(
            row.objekt_version_tag_objekt_version.version_id,
            "a" * 32,
        )

    def test_version_relationship_to_tags(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(self._tag(tag_key="owner", tag_value="alice"))
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektVersion)
            .where(ObjektVersion.id == self.version.id)
            .options(selectinload(ObjektVersion.objekt_version_tags)),
        )

        keys = sorted(item.tag_key for item in loaded.objekt_version_tags)
        self.assertEqual(keys, ["color", "owner"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._tag())
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektVersion).where(ObjektVersion.id == self.version.id),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.objekt_version_tags

    def test_cascade_delete_with_version(self):
        self.session.add(self._tag())
        self.session.commit()

        self.session.delete(self.version)
        self.session.commit()

        remaining = self.session.scalars(select(ObjektVersionTag)).all()
        self.assertEqual(remaining, [])
