# app/constants.py
# SPDX-License-Identifier: GPL-3.0-only

# NOTE (ADR-01): Source code follows project conventions.
# 1. File names use `<resource>_<action>` to group related logic by
#    domain resource and improve locality in listings.
# 2. Function names use `<action>_<resource>` to preserve natural
#    reading order and improve readability.
# 3. Code style follows PEP 8 with line length limits: 79 characters
#    for code and 72 characters for comments, enforced with flake8.
# 4. Path-related constants follow suffix conventions:
#    *_PATH     - absolute file path
#    *_DIR      - absolute directory path
#    *_DIRNAME  - relative directory name
#    *_FILENAME - relative filename

GOCRYPTFS_MASTER_PASSWORD_MIN_LENGTH = 16
GOCRYPTFS_PASSPHRASE_LENGTH = 80
GOCRYPTFS_PASSPHRASE_FILENAME = "gocryptfs_passphrase.enc"

FERNET_ENCRYPTION_KEY_FILENAME = "fernet_encryption.key"

FILE_CHUNK_SIZE_BYTES = 1024 * 64
FILE_MIMETYPE_READ_BYTES = 1024 * 16
