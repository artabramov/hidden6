# app/xml/multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.etree import ElementTree
from xml.sax.saxutils import escape

from pydantic import ValidationError

from app.constants import S3_XMLNS
from app.s3.etag_normalize import etag_normalize
from app.schemas.multipart_complete import MultipartPart


def parse_complete_multipart_xml(body: bytes) -> list[MultipartPart]:
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


def render_complete_multipart_xml(
    bucket_name: str,
    object_key: str,
    etag: str,
) -> str:
    """
    Render an S3-compatible XML response for CompleteMultipartUpload,
    carrying the location and the ETag of the assembled object.
    """
    location = f"/{bucket_name}/{object_key}"
    quoted_etag = f'"{etag}"'

    return "".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<CompleteMultipartUploadResult xmlns="{S3_XMLNS}">',
        f"<Location>{escape(location)}</Location>",
        f"<Bucket>{escape(bucket_name)}</Bucket>",
        f"<Key>{escape(object_key)}</Key>",
        f"<ETag>{escape(quoted_etag)}</ETag>",
        "</CompleteMultipartUploadResult>",
    ])


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
