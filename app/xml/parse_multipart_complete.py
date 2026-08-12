# app/xml/parse_multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.etree import ElementTree

from pydantic import ValidationError

from app.s3.etag_normalize import etag_normalize
from app.schemas.multipart_complete import MultipartPart


def parse_multipart_complete(body: bytes) -> list[MultipartPart]:
    """
    Parse a CompleteMultipartUpload request body into the parts the
    client wants assembled. Element namespaces are ignored, matching
    clients that send the body with or without one.

    Raises:
        ValueError: Body is not a well formed part list.
    """
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("Malformed CompleteMultipartUpload.") from exc

    if _local_name(root.tag) != "CompleteMultipartUpload":
        raise ValueError("Malformed CompleteMultipartUpload.")

    parts = [
        _build_part(element)
        for element in root
        if _local_name(element.tag) == "Part"
    ]

    if not parts:
        raise ValueError("Malformed CompleteMultipartUpload.")

    return parts


def _build_part(element: ElementTree.Element) -> MultipartPart:
    """Build a listed part from its Part element."""
    values: dict[str, str] = {}

    for child in element:
        name = _local_name(child.tag)

        if name in ("PartNumber", "ETag") and child.text:
            values[name] = child.text.strip()

    try:
        return MultipartPart(
            part_number=int(values.get("PartNumber", "")),
            etag=etag_normalize(values.get("ETag", "")),
        )
    except (ValidationError, ValueError) as exc:
        raise ValueError("Malformed CompleteMultipartUpload.") from exc


def _local_name(tag: str) -> str:
    """Return an element name without its namespace prefix."""
    return tag.rsplit("}", 1)[-1]
