# tests/s3/test_object_lock.py
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from tests.helpers import set_minimal_app_config_env


set_minimal_app_config_env()

from app.constants import (  # noqa: E402
    BUCKET_VERSIONING_DISABLED,
    BUCKET_VERSIONING_ENABLED,
    BUCKET_VERSIONING_SUSPENDED,
)
from app.db.engine import load_all_models  # noqa: E402
from app.errors import S3BucketStateInvalidError  # noqa: E402
from app.models.bucket import Bucket  # noqa: E402
from app.models.object_version import ObjectVersion  # noqa: E402, F401
from app.models.object_version_metadata import (  # noqa: E402, F401
    ObjectVersionMetadata,
)
from app.models.object_version_tag import ObjectVersionTag  # noqa: E402, F401
from app.s3.object_lock import set_bucket_object_lock_configuration  # noqa: E402

load_all_models()

RESOURCE = "/photos"


class TestSetBucketObjektLockConfiguration(unittest.TestCase):
    def _bucket(self, **kwargs) -> Bucket:
        values = {
            "id": 1,
            "user_id": 1,
            "bucket_name": "photos",
            "versioning_status": BUCKET_VERSIONING_ENABLED,
            "object_lock_enabled": False,
        }
        values.update(kwargs)
        return Bucket(**values)

    def _set(self, bucket, **kwargs) -> None:
        defaults = {
            "objekt_lock_enabled": None,
            "default_lock_mode": None,
            "default_retention_days": None,
            "default_retention_years": None,
            "resource": RESOURCE,
        }
        defaults.update(kwargs)
        set_bucket_object_lock_configuration(bucket, **defaults)

    def test_enables_object_lock(self):
        bucket = self._bucket()

        self._set(bucket, objekt_lock_enabled="Enabled")

        self.assertTrue(bucket.object_lock_enabled)
        self.assertIsNone(bucket.default_lock_mode)
        self.assertIsNone(bucket.default_retention_days)
        self.assertIsNone(bucket.default_retention_years)

    def test_sets_governance_days(self):
        bucket = self._bucket()

        self._set(
            bucket,
            objekt_lock_enabled="Enabled",
            default_lock_mode="GOVERNANCE",
            default_retention_days=10,
        )

        self.assertTrue(bucket.object_lock_enabled)
        self.assertEqual(bucket.default_lock_mode, "GOVERNANCE")
        self.assertEqual(bucket.default_retention_days, 10)
        self.assertIsNone(bucket.default_retention_years)

    def test_sets_compliance_years(self):
        bucket = self._bucket()

        self._set(
            bucket,
            objekt_lock_enabled="Enabled",
            default_lock_mode="COMPLIANCE",
            default_retention_years=2,
        )

        self.assertTrue(bucket.object_lock_enabled)
        self.assertEqual(bucket.default_lock_mode, "COMPLIANCE")
        self.assertIsNone(bucket.default_retention_days)
        self.assertEqual(bucket.default_retention_years, 2)

    def test_clears_default_rule_without_disabling_lock(self):
        bucket = self._bucket(
            object_lock_enabled=True,
            default_lock_mode="GOVERNANCE",
            default_retention_days=10,
        )

        self._set(bucket)

        self.assertTrue(bucket.object_lock_enabled)
        self.assertIsNone(bucket.default_lock_mode)
        self.assertIsNone(bucket.default_retention_days)
        self.assertIsNone(bucket.default_retention_years)

    def test_updates_default_rule_when_already_enabled(self):
        bucket = self._bucket(
            object_lock_enabled=True,
            default_lock_mode="GOVERNANCE",
            default_retention_days=10,
        )

        self._set(
            bucket,
            default_lock_mode="COMPLIANCE",
            default_retention_years=2,
        )

        self.assertTrue(bucket.object_lock_enabled)
        self.assertEqual(bucket.default_lock_mode, "COMPLIANCE")
        self.assertIsNone(bucket.default_retention_days)
        self.assertEqual(bucket.default_retention_years, 2)

    def test_missing_enabled_does_not_enable_lock(self):
        bucket = self._bucket()

        self._set(
            bucket,
            default_lock_mode="GOVERNANCE",
            default_retention_days=10,
        )

        self.assertFalse(bucket.object_lock_enabled)
        self.assertEqual(bucket.default_lock_mode, "GOVERNANCE")
        self.assertEqual(bucket.default_retention_days, 10)

    def test_non_enabled_flag_does_not_enable_lock(self):
        bucket = self._bucket()

        self._set(bucket, objekt_lock_enabled="Disabled")

        self.assertFalse(bucket.object_lock_enabled)

    def test_rejects_when_versioning_disabled(self):
        bucket = self._bucket(versioning_status=BUCKET_VERSIONING_DISABLED)

        with self.assertRaises(S3BucketStateInvalidError) as cm:
            self._set(bucket, objekt_lock_enabled="Enabled")

        self.assertEqual(cm.exception.resource, RESOURCE)
        self.assertFalse(bucket.object_lock_enabled)

    def test_rejects_when_versioning_suspended(self):
        bucket = self._bucket(versioning_status=BUCKET_VERSIONING_SUSPENDED)

        with self.assertRaises(S3BucketStateInvalidError) as cm:
            self._set(bucket, objekt_lock_enabled="Enabled")

        self.assertEqual(cm.exception.resource, RESOURCE)
        self.assertFalse(bucket.object_lock_enabled)
