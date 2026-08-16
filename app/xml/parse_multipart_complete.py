# app/xml/parse_multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.etree import ElementTree

from pydantic import ValidationError

from app.s3.etag import normalize_etag
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

    if _strip_element(root.tag) != "CompleteMultipartUpload":
        raise ValueError("Malformed CompleteMultipartUpload.")

    parts = [
        _parse_element(element)
        for element in root
        if _strip_element(element.tag) == "Part"
    ]

    if not parts:
        raise ValueError("Malformed CompleteMultipartUpload.")

    return parts


def _parse_element(element: ElementTree.Element) -> MultipartPart:
    """Parse a single listed part from its Part element."""
    values: dict[str, str] = {}

    for child in element:
        name = _strip_element(child.tag)

        if name in ("PartNumber", "ETag") and child.text:
            values[name] = child.text.strip()

    try:
        return MultipartPart(
            part_number=int(values.get("PartNumber", "")),
            etag=normalize_etag(values.get("ETag", "")),
        )
    except (ValidationError, ValueError) as exc:
        raise ValueError("Malformed CompleteMultipartUpload.") from exc


def _strip_element(tag: str) -> str:
    """Return an element name without its namespace prefix."""
    return tag.rsplit("}", 1)[-1]
