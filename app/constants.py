# app/constants.py
# SPDX-License-Identifier: GPL-3.0-only

HIDDEN_TITLE = "Hidden — S3-compatible storage powered by gocryptfs"

# Watchdog heartbeat file and drain timeout before unmount.
# Used for liveness checks and emergency unmount coordination.
WATCHDOG_HEARTBEAT_PATH = "/tmp/hidden-watchdog.touch"
WATCHDOG_GRACEFUL_UNMOUNT_SECONDS = 5

GOCRYPTFS_PASSPHRASE_LENGTH = 80
GOCRYPTFS_PASSPHRASE_FILENAME = "gocryptfs_passphrase.enc"

FERNET_ENCRYPTION_KEY_FILENAME = "fernet_encryption.key"

MOUNTPOINT_DB_DIRNAME = "db"
MOUNTPOINT_BUCKETS_DIRNAME = "buckets"
MOUNTPOINT_VERSIONS_DIRNAME = "versions"
MOUNTPOINT_TMP_DIRNAME = "tmp"

FILE_CHUNK_SIZE_BYTES = 1024 * 64
FILE_MIMETYPE_READ_BYTES = 1024 * 16
