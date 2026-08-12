# tests/schemas/test_objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from pydantic import ValidationError

from app.schemas.objekt_upload import ObjektUploadRequest


class TestObjektUploadRequest(unittest.TestCase):
    def test_accepts_valid_object_key(self):
        data = ObjektUploadRequest(object_key="photos/cat.png")
        self.assertEqual(data.object_key, "photos/cat.png")

    def test_rejects_invalid_object_key(self):
        with self.assertRaises(ValidationError):
            ObjektUploadRequest(object_key="photos/../cat.png")

    def test_rejects_empty_object_key(self):
        with self.assertRaises(ValidationError):
            ObjektUploadRequest(object_key="")

    def test_rejects_extra_fields(self):
        with self.assertRaises(ValidationError):
            ObjektUploadRequest(object_key="cat.png", extra="nope")

    def test_requires_object_key(self):
        with self.assertRaises(ValidationError):
            ObjektUploadRequest()
