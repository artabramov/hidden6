# tests/models/test_objekt_multipart_tag.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.db.base import Base  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.objekt_metadata import ObjektMetadata  # noqa: E402, F401
from app.models.objekt_multipart import ObjektMultipart  # noqa: E402
from app.models.objekt_multipart_metadata import ObjektMultipartMetadata  # noqa: E402, F401
from app.models.objekt_multipart_tag import ObjektMultipartTag  # noqa: E402
from app.models.objekt_tag import ObjektTag  # noqa: E402, F401
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
from app.models.objekt_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
from app.models.objekt_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjektMultipartTagModel(unittest.TestCase):

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

    def _tag(self, **kwargs) -> ObjektMultipartTag:
        defaults = {
            "objekt_multipart_id": self.multipart.id,
            "tag_key": "color",
            "tag_value": "red",
        }
        defaults.update(kwargs)
        return ObjektMultipartTag(**defaults)

    def test_tablename(self):
        self.assertEqual(
            ObjektMultipartTag.__tablename__,
            "objekts_multiparts_tags",
        )

    def test_persists_required_fields(self):
        row = self._tag(tag_key="owner", tag_value="alice")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertIsNotNone(row.id)
        self.assertEqual(row.objekt_multipart_id, self.multipart.id)
        self.assertEqual(row.tag_key, "owner")
        self.assertEqual(row.tag_value, "alice")

    def test_empty_tag_value_is_allowed(self):
        row = self._tag(tag_key="blank", tag_value="")
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.tag_value, "")

    def test_tag_key_unique_per_multipart(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.commit()

        self.session.add(self._tag(tag_key="color", tag_value="blue"))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_tag_key_allowed_on_different_multiparts(self):
        other = ObjektMultipart(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            upload_id="b" * 32,
            object_key="b.txt",
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(
            self._tag(
                objekt_multipart_id=other.id,
                tag_key="color",
                tag_value="blue",
            ),
        )
        self.session.commit()

        rows = self.session.scalars(select(ObjektMultipartTag)).all()
        self.assertEqual(len(rows), 2)

    def test_relationship_back_to_multipart(self):
        row = self._tag()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(
            row.objekt_multipart_tag_objekt_multipart.id,
            self.multipart.id,
        )
        self.assertEqual(
            row.objekt_multipart_tag_objekt_multipart.upload_id,
            "a" * 32,
        )

    def test_multipart_relationship_to_tags(self):
        self.session.add(self._tag(tag_key="color", tag_value="red"))
        self.session.add(self._tag(tag_key="owner", tag_value="alice"))
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipart)
            .where(ObjektMultipart.id == self.multipart.id)
            .options(selectinload(ObjektMultipart.objekt_multipart_tags)),
        )

        keys = sorted(item.tag_key for item in loaded.objekt_multipart_tags)
        self.assertEqual(keys, ["color", "owner"])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._tag())
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipart).where(
                ObjektMultipart.id == self.multipart.id,
            ),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.objekt_multipart_tags

    def test_cascade_delete_with_multipart(self):
        self.session.add(self._tag())
        self.session.commit()

        self.session.delete(self.multipart)
        self.session.commit()

        remaining = self.session.scalars(select(ObjektMultipartTag)).all()
        self.assertEqual(remaining, [])
