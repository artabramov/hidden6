# tests/xml/test_render_object_list.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.models.objekt import Objekt  # noqa: E402
from app.xml.render_object_list import render_object_list  # noqa: E402


def _objekt(key: str, size: int = 10, etag: str = "abc", modified_at: int = 1_704_067_200) -> Objekt:
    return Objekt(
        id=1,
        bucket_id=1,
        user_id=1,
        object_key=key,
        size_bytes=size,
        etag=etag,
        content_type="application/octet-stream",
        created_at=1_704_067_200,
        modified_at=modified_at,
    )


class TestRenderObjektList(unittest.TestCase):
    def test_render_empty_list(self):
        xml = render_object_list(
            bucket_name="photos",
            prefix="",
            max_keys=1000,
            objekts=[],
        )

        self.assertIn("<ListBucketResult", xml)
        self.assertIn("<Name>photos</Name>", xml)
        self.assertIn("<Prefix></Prefix>", xml)
        self.assertIn("<MaxKeys>1000</MaxKeys>", xml)
        self.assertIn("<KeyCount>0</KeyCount>", xml)
        self.assertIn("<IsTruncated>false</IsTruncated>", xml)
        self.assertNotIn("<Contents>", xml)

    def test_render_single_object(self):
        obj = _objekt("photo.jpg", size=1234, etag="deadbeef", modified_at=1_704_067_200)
        xml = render_object_list(
            bucket_name="photos",
            prefix="",
            max_keys=1000,
            objekts=[obj],
        )

        self.assertIn("<Key>photo.jpg</Key>", xml)
        self.assertIn("<Size>1234</Size>", xml)
        self.assertIn("<ETag>&quot;deadbeef&quot;</ETag>", xml)
        self.assertIn("<LastModified>2024-01-01T00:00:00.000Z</LastModified>", xml)
        self.assertIn("<StorageClass>STANDARD</StorageClass>", xml)
        self.assertIn("<KeyCount>1</KeyCount>", xml)
        self.assertIn("<IsTruncated>false</IsTruncated>", xml)

    def test_uses_modified_at_for_last_modified(self):
        obj = _objekt("file.txt", modified_at=1_704_153_600)
        xml = render_object_list(
            bucket_name="my-bucket",
            prefix="",
            max_keys=1000,
            objekts=[obj],
        )

        self.assertIn("<LastModified>2024-01-02T00:00:00.000Z</LastModified>", xml)
        self.assertNotIn("2024-01-01", xml)

    def test_is_truncated_when_result_equals_max_keys(self):
        objekts = [_objekt(f"file{i}.txt") for i in range(5)]
        xml = render_object_list(
            bucket_name="my-bucket",
            prefix="",
            max_keys=5,
            objekts=objekts,
        )

        self.assertIn("<IsTruncated>true</IsTruncated>", xml)

    def test_is_not_truncated_when_result_below_max_keys(self):
        objekts = [_objekt(f"file{i}.txt") for i in range(3)]
        xml = render_object_list(
            bucket_name="my-bucket",
            prefix="",
            max_keys=5,
            objekts=objekts,
        )

        self.assertIn("<IsTruncated>false</IsTruncated>", xml)

    def test_renders_prefix_in_response(self):
        xml = render_object_list(
            bucket_name="my-bucket",
            prefix="2024/",
            max_keys=1000,
            objekts=[],
        )

        self.assertIn("<Prefix>2024/</Prefix>", xml)

    def test_escapes_xml_special_characters(self):
        obj = _objekt("a&b/<c>.txt")
        xml = render_object_list(
            bucket_name="my&bucket",
            prefix="",
            max_keys=1000,
            objekts=[obj],
        )

        self.assertIn("<Name>my&amp;bucket</Name>", xml)
        self.assertIn("<Key>a&amp;b/&lt;c&gt;.txt</Key>", xml)

    def test_multiple_objects_all_rendered(self):
        objekts = [
            _objekt("a.txt", size=1),
            _objekt("b.txt", size=2),
            _objekt("c.txt", size=3),
        ]
        xml = render_object_list(
            bucket_name="my-bucket",
            prefix="",
            max_keys=1000,
            objekts=objekts,
        )

        self.assertIn("<Key>a.txt</Key>", xml)
        self.assertIn("<Key>b.txt</Key>", xml)
        self.assertIn("<Key>c.txt</Key>", xml)
        self.assertIn("<KeyCount>3</KeyCount>", xml)
