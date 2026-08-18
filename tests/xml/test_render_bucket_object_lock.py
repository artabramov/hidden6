# tests/xml/test_render_bucket_object_lock.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import BUCKET_VERSIONING_ENABLED, S3_XMLNS  # noqa: E402
from app.db.engine import load_all_models  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.xml.render_bucket_object_lock import (  # noqa: E402
    render_bucket_object_lock,
)

load_all_models()


class TestRenderBucketObjektLock(unittest.TestCase):
    def _bucket(self, **kwargs) -> Bucket:
        values = {
            "id": 1,
            "user_id": 1,
            "bucket_name": "photos",
            "versioning_status": BUCKET_VERSIONING_ENABLED,
            "object_lock_enabled": True,
        }
        values.update(kwargs)
        return Bucket(**values)

    def test_renders_enabled_without_default_rule(self):
        xml = render_bucket_object_lock(self._bucket())

        self.assertEqual(
            xml,
            (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f'<ObjectLockConfiguration xmlns="{S3_XMLNS}">'
                "<ObjectLockEnabled>Enabled</ObjectLockEnabled>"
                "</ObjectLockConfiguration>"
            ),
        )
        self.assertNotIn("<Rule>", xml)
        self.assertNotIn("<DefaultRetention>", xml)

    def test_renders_governance_days(self):
        xml = render_bucket_object_lock(
            self._bucket(
                default_lock_mode="GOVERNANCE",
                default_retention_days=10,
            ),
        )

        self.assertIn(f'xmlns="{S3_XMLNS}"', xml)
        self.assertIn("<ObjectLockEnabled>Enabled</ObjectLockEnabled>", xml)
        self.assertIn("<Mode>GOVERNANCE</Mode>", xml)
        self.assertIn("<Days>10</Days>", xml)
        self.assertNotIn("<Years>", xml)

    def test_renders_compliance_years(self):
        xml = render_bucket_object_lock(
            self._bucket(
                default_lock_mode="COMPLIANCE",
                default_retention_years=2,
            ),
        )

        self.assertIn("<Mode>COMPLIANCE</Mode>", xml)
        self.assertIn("<Years>2</Years>", xml)
        self.assertNotIn("<Days>", xml)
