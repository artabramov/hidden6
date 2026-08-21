# app/constants.py
# SPDX-License-Identifier: GPL-3.0-only

HIDDEN_TITLE = "Hidden — S3-compatible storage secured by gocryptfs"

GOCRYPTFS_PASSPHRASE_LENGTH = 80
GOCRYPTFS_PASSPHRASE_FILENAME = "gocryptfs_passphrase.enc"

WATCHDOG_HEARTBEAT_PATH = "/tmp/gocryptfs-watchdog.touch"

FERNET_ENCRYPTION_KEY_FILENAME = "fernet_encryption.key"

MOUNTPOINT_DB_DIRNAME = "db"
MOUNTPOINT_BUCKETS_DIRNAME = "buckets"
MOUNTPOINT_VERSIONS_DIRNAME = "versions"
MOUNTPOINT_TMP_DIRNAME = "tmp"

FILE_CHUNK_SIZE_BYTES = 1024 * 64
FILE_MIMETYPE_READ_BYTES = 1024 * 16

SECONDS_PER_DAY = 24 * 60 * 60
SECONDS_PER_YEAR = 365 * SECONDS_PER_DAY

# S3 bucket versioning statuses.
BUCKET_VERSIONING_DISABLED = "Disabled"
BUCKET_VERSIONING_ENABLED = "Enabled"
BUCKET_VERSIONING_SUSPENDED = "Suspended"

OBJECT_KEY_MAX_BYTES = 1024
OBJECT_CONTENT_TYPE_DEFAULT = "application/octet-stream"

# S3 allows 10000 parts per multipart upload, and every part except
# the last one must be at least 5 MiB.
OBJECT_PART_NUMBER_MAX = 10000
OBJECT_PART_SIZE_MIN_BYTES = 1024 * 1024 * 5

S3_XMLNS = "http://s3.amazonaws.com/doc/2006-03-01/"

USER_ROOT_USERNAME = "root"
USER_ACCESS_KEY_ID_LENGTH = 20
USER_SECRET_ACCESS_KEY_LENGTH = 40
