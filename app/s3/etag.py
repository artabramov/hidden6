# app/s3/etag.py
# SPDX-License-Identifier: GPL-3.0-only

import hashlib


def normalize_etag(value: str) -> str:
    """
    Reduce an ETag to the bare hash it stands for. S3 carries ETags
    wrapped in quotes on the wire, and clients echo them back with the
    quotes kept, dropped, or upper-cased, so a listed part matches a
    stored one only after the quoting is stripped away.
    """
    return value.strip().strip('"').lower()


def construct_etag(part_hashes: list[str]) -> str:
    """
    Build the ETag of an assembled object: the MD5 of the concatenated
    part digests, suffixed with the number of parts. Unlike the ETag of
    a single upload it is not the hash of the stored bytes, which is
    how clients tell an assembled object apart.
    """
    digests = b"".join(bytes.fromhex(value) for value in part_hashes)
    digest = hashlib.md5(digests, usedforsecurity=False).hexdigest()

    return f"{digest}-{len(part_hashes)}"
