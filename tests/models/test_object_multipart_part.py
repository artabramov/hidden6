# tests/models/test_object_multipart_part.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, selectinload

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import OBJECT_PART_NUMBER_MAX  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.bucket_tag import BucketTag  # noqa: E402, F401
from app.models.objekt import Objekt  # noqa: E402, F401
from app.models.object_metadata import ObjektMetadata  # noqa: E402, F401
from app.models.object_multipart import ObjektMultipart  # noqa: E402
from app.models.object_multipart_metadata import ObjektMultipartMetadata  # noqa: E402, F401
from app.models.object_multipart_part import ObjektMultipartPart  # noqa: E402
from app.models.object_multipart_tag import ObjektMultipartTag  # noqa: E402, F401
from app.models.object_tag import ObjektTag  # noqa: E402, F401
from app.models.object_version import ObjektVersion  # noqa: E402, F401
from app.models.object_version_metadata import ObjektVersionMetadata  # noqa: E402, F401
from app.models.object_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.models.user import User  # noqa: E402
from app.models.user_key import UserKey  # noqa: E402, F401


class TestObjektMultipartPartModel(unittest.TestCase):

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

    def _part(self, **kwargs) -> ObjektMultipartPart:
        defaults = {
            "objekt_multipart_id": self.multipart.id,
            "part_number": 1,
            "size_bytes": 5 * 1024 * 1024,
            "etag": "a" * 32,
        }
        defaults.update(kwargs)
        return ObjektMultipartPart(**defaults)

    def _assert_rejects(self, part):
        self.session.add(part)
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_tablename(self):
        self.assertEqual(
            ObjektMultipartPart.__tablename__,
            "objekts_multiparts_parts",
        )

    def test_persists_required_fields_and_defaults(self):
        row = self._part(
            part_number=3,
            size_bytes=1024,
            etag="b" * 32,
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertIsNotNone(row.id)
        self.assertEqual(row.objekt_multipart_id, self.multipart.id)
        self.assertEqual(row.part_number, 3)
        self.assertEqual(row.size_bytes, 1024)
        self.assertEqual(row.etag, "b" * 32)
        self.assertIsInstance(row.modified_at, int)

    def test_modified_at_can_be_set(self):
        row = self._part(modified_at=1_704_067_200)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.modified_at, 1_704_067_200)

    def test_part_number_unique_per_multipart(self):
        self.session.add(self._part(part_number=1, etag="a" * 32))
        self.session.commit()

        self.session.add(self._part(part_number=1, etag="b" * 32))
        with self.assertRaises(IntegrityError):
            self.session.commit()

    def test_same_part_number_allowed_on_different_multiparts(self):
        other = ObjektMultipart(
            bucket_id=self.bucket.id,
            user_id=self.user.id,
            upload_id="b" * 32,
            object_key="b.txt",
        )
        self.session.add(other)
        self.session.commit()
        self.session.refresh(other)

        self.session.add(self._part(part_number=1, etag="a" * 32))
        self.session.add(
            self._part(
                objekt_multipart_id=other.id,
                part_number=1,
                etag="b" * 32,
            ),
        )
        self.session.commit()

        rows = self.session.scalars(select(ObjektMultipartPart)).all()
        self.assertEqual(len(rows), 2)

    def test_part_number_min_is_one(self):
        self._assert_rejects(self._part(part_number=0))

    def test_part_number_max_is_allowed(self):
        row = self._part(part_number=OBJECT_PART_NUMBER_MAX)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.part_number, OBJECT_PART_NUMBER_MAX)

    def test_part_number_above_max_is_rejected(self):
        self._assert_rejects(self._part(part_number=OBJECT_PART_NUMBER_MAX + 1))

    def test_size_bytes_must_be_nonnegative(self):
        self._assert_rejects(self._part(size_bytes=-1))

    def test_zero_size_bytes_is_allowed(self):
        row = self._part(size_bytes=0)
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)

        self.assertEqual(row.size_bytes, 0)

    def test_relationship_back_to_multipart(self):
        row = self._part()
        self.session.add(row)
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipartPart)
            .where(ObjektMultipartPart.id == row.id)
            .options(
                selectinload(
                    ObjektMultipartPart.objekt_multipart_part_objekt_multipart,
                ),
            ),
        )

        self.assertEqual(
            loaded.objekt_multipart_part_objekt_multipart.id,
            self.multipart.id,
        )
        self.assertEqual(
            loaded.objekt_multipart_part_objekt_multipart.upload_id,
            "a" * 32,
        )

    def test_multipart_relationship_to_parts(self):
        self.session.add(self._part(part_number=1, etag="a" * 32))
        self.session.add(self._part(part_number=2, etag="b" * 32))
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipart)
            .where(ObjektMultipart.id == self.multipart.id)
            .options(selectinload(ObjektMultipart.objekt_multipart_parts)),
        )

        numbers = sorted(item.part_number for item in loaded.objekt_multipart_parts)
        self.assertEqual(numbers, [1, 2])

    def test_relationship_access_without_eager_load_raises(self):
        self.session.add(self._part())
        self.session.commit()

        loaded = self.session.scalar(
            select(ObjektMultipart).where(
                ObjektMultipart.id == self.multipart.id,
            ),
        )

        with self.assertRaises(InvalidRequestError):
            _ = loaded.objekt_multipart_parts

    def test_multipart_delete_is_restricted(self):
        self.session.add(self._part())
        self.session.commit()

        # FK has no ON DELETE CASCADE; Core DELETE exercises the
        # database constraint (ORM cascade would still remove parts).
        with self.assertRaises(IntegrityError):
            self.session.execute(
                delete(ObjektMultipart).where(
                    ObjektMultipart.id == self.multipart.id,
                ),
            )
            self.session.commit()
