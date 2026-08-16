# tests/s3/test_versioning.py
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
from app.models.bucket import Bucket  # noqa: E402
from app.models.objekt_version import ObjektVersion  # noqa: E402, F401
from app.models.objekt_version_metadata import (  # noqa: E402, F401
    ObjektVersionMetadata,
)
from app.models.objekt_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.s3.versioning import (  # noqa: E402
    get_bucket_versioning_status,
    set_bucket_versioning_status,
)

load_all_models()


class TestGetBucketVersioningStatus(unittest.TestCase):
    def test_disabled_exposes_no_status(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_DISABLED,
        )

        self.assertIsNone(get_bucket_versioning_status(bucket))

    def test_enabled_returns_s3_status(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
        )

        self.assertEqual(
            get_bucket_versioning_status(bucket),
            BUCKET_VERSIONING_ENABLED,
        )

    def test_suspended_returns_s3_status(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_SUSPENDED,
        )

        self.assertEqual(
            get_bucket_versioning_status(bucket),
            BUCKET_VERSIONING_SUSPENDED,
        )


class TestSetBucketVersioningStatus(unittest.TestCase):
    def test_enables_from_disabled(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_DISABLED,
        )

        set_bucket_versioning_status(bucket, BUCKET_VERSIONING_ENABLED)

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )

    def test_suspends_from_enabled(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
        )

        set_bucket_versioning_status(bucket, BUCKET_VERSIONING_SUSPENDED)

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_SUSPENDED,
        )

    def test_reenables_from_suspended(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_SUSPENDED,
        )

        set_bucket_versioning_status(bucket, BUCKET_VERSIONING_ENABLED)

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )

    def test_rejects_suspend_from_disabled(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_DISABLED,
        )

        with self.assertRaises(ValueError) as cm:
            set_bucket_versioning_status(
                bucket,
                BUCKET_VERSIONING_SUSPENDED,
            )

        self.assertIn(
            "cannot be suspended before it is enabled",
            str(cm.exception),
        )
        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_DISABLED,
        )

    def test_rejects_disabled_status(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
        )

        with self.assertRaises(ValueError) as cm:
            set_bucket_versioning_status(
                bucket,
                BUCKET_VERSIONING_DISABLED,
            )

        self.assertIn("Invalid bucket versioning status", str(cm.exception))
        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )

    def test_rejects_unknown_status(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
        )

        with self.assertRaises(ValueError) as cm:
            set_bucket_versioning_status(bucket, "Invalid")

        self.assertIn("Invalid bucket versioning status", str(cm.exception))
        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )
