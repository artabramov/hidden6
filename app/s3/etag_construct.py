# app/s3/etag_construct.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib


def etag_construct(part_hashes: list[str]) -> str:
    """
    Build the ETag of an assembled object: the MD5 of the concatenated
    part digests, suffixed with the number of parts. Unlike the ETag of
    a single upload it is not the hash of the stored bytes, which is
    how clients tell an assembled object apart.
    """
    digests = b"".join(bytes.fromhex(value) for value in part_hashes)
    digest = hashlib.md5(digests, usedforsecurity=False).hexdigest()

    return f"{digest}-{len(part_hashes)}"
