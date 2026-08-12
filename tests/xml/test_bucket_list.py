# tests/xml/test_bucket_list.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.models.bucket import Bucket  # noqa: E402
from app.models.user import User  # noqa: E402
from app.xml.bucket_list import render_list_buckets_xml  # noqa: E402


class TestBucketListXml(unittest.TestCase):
    def test_render_empty_list(self):
        owner = User(id=1, username="root", is_root=True)
        xml = render_list_buckets_xml(owner=owner, buckets=[])

        self.assertIn("<ListAllMyBucketsResult", xml)
        self.assertIn("<ID>1</ID>", xml)
        self.assertIn("<DisplayName>root</DisplayName>", xml)
        self.assertIn("<Buckets></Buckets>", xml)
        self.assertNotIn("<Bucket>", xml)

    def test_render_buckets_sorted_by_caller(self):
        owner = User(id=2, username="alice", is_root=False)
        buckets = [
            Bucket(user_id=2, bucket_name="alpha", created_at=1_704_067_200),
            Bucket(user_id=2, bucket_name="beta", created_at=1_704_153_600),
        ]
        xml = render_list_buckets_xml(owner=owner, buckets=buckets)

        self.assertIn("<Name>alpha</Name>", xml)
        self.assertIn("<Name>beta</Name>", xml)
        self.assertIn(
            "<CreationDate>2024-01-01T00:00:00.000Z</CreationDate>",
            xml,
        )
        self.assertIn(
            "<CreationDate>2024-01-02T00:00:00.000Z</CreationDate>",
            xml,
        )

    def test_escapes_xml_special_characters(self):
        owner = User(id=1, username="a&b", is_root=True)
        buckets = [
            Bucket(user_id=1, bucket_name="x<y", created_at=1_704_067_200),
        ]
        xml = render_list_buckets_xml(owner=owner, buckets=buckets)

        self.assertIn("<DisplayName>a&amp;b</DisplayName>", xml)
        self.assertIn("<Name>x&lt;y</Name>", xml)
