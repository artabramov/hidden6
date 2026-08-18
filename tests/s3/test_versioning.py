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
from app.errors import (  # noqa: E402
    S3BucketStateInvalidError,
    S3IllegalVersioningConfigurationError,
)
from app.models.bucket import Bucket  # noqa: E402
from app.models.object_version import ObjektVersion  # noqa: E402, F401
from app.models.object_version_metadata import (  # noqa: E402, F401
    ObjektVersionMetadata,
)
from app.models.object_version_tag import ObjektVersionTag  # noqa: E402, F401
from app.s3.versioning import (  # noqa: E402
    get_bucket_versioning_status,
    set_bucket_versioning_status,
)

load_all_models()

RESOURCE = "/photos"


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

        set_bucket_versioning_status(
            bucket,
            BUCKET_VERSIONING_ENABLED,
            RESOURCE,
        )

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )

    def test_suspends_from_disabled(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_DISABLED,
        )

        set_bucket_versioning_status(
            bucket,
            BUCKET_VERSIONING_SUSPENDED,
            RESOURCE,
        )

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_SUSPENDED,
        )

    def test_suspends_from_enabled(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
        )

        set_bucket_versioning_status(
            bucket,
            BUCKET_VERSIONING_SUSPENDED,
            RESOURCE,
        )

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

        set_bucket_versioning_status(
            bucket,
            BUCKET_VERSIONING_ENABLED,
            RESOURCE,
        )

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )

    def test_enables_when_object_lock_enabled(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
        )

        set_bucket_versioning_status(
            bucket,
            BUCKET_VERSIONING_ENABLED,
            RESOURCE,
        )

        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )

    def test_rejects_suspend_when_object_lock_enabled(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
            object_lock_enabled=True,
        )

        with self.assertRaises(S3BucketStateInvalidError) as cm:
            set_bucket_versioning_status(
                bucket,
                BUCKET_VERSIONING_SUSPENDED,
                RESOURCE,
            )

        self.assertEqual(cm.exception.resource, RESOURCE)
        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )

    def test_rejects_disabled_status(self):
        bucket = Bucket(
            id=1,
            user_id=1,
            bucket_name="photos",
            versioning_status=BUCKET_VERSIONING_ENABLED,
        )

        with self.assertRaises(S3IllegalVersioningConfigurationError) as cm:
            set_bucket_versioning_status(
                bucket,
                BUCKET_VERSIONING_DISABLED,
                RESOURCE,
            )

        self.assertEqual(cm.exception.resource, RESOURCE)
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

        with self.assertRaises(S3IllegalVersioningConfigurationError) as cm:
            set_bucket_versioning_status(bucket, "Invalid", RESOURCE)

        self.assertEqual(cm.exception.resource, RESOURCE)
        self.assertEqual(
            bucket.versioning_status,
            BUCKET_VERSIONING_ENABLED,
        )
