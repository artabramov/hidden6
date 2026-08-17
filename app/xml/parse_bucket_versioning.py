# app/xml/parse_bucket_versioning.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.etree import ElementTree


def parse_bucket_versioning(body: bytes) -> str:
    """
    Parse a PutBucketVersioning request body and return its Status.

    Element namespaces are ignored, matching clients that send the
    body with or without the S3 namespace.

    Raises:
        ValueError: Body is not a well formed VersioningConfiguration.
    """
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("Malformed VersioningConfiguration.") from exc

    if _strip_element(root.tag) != "VersioningConfiguration":
        raise ValueError("Malformed VersioningConfiguration.")

    versioning_status = None

    for element in root:
        if _strip_element(element.tag) == "Status" and element.text:
            versioning_status = element.text.strip()
            break

    if not versioning_status:
        raise ValueError("Malformed VersioningConfiguration.")

    return versioning_status


def _strip_element(tag: str) -> str:
    """Return an element name without its namespace prefix."""
    return tag.rsplit("}", 1)[-1]
