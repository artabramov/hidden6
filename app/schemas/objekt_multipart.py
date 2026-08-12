# app/schemas/objekt_multipart.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.etree import ElementTree
from xml.sax.saxutils import escape

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.constants import S3_XMLNS


class MultipartPart(BaseModel):
    """
    One part listed by the client in a CompleteMultipartUpload request.
    The ETag is normalized to the bare hash of the uploaded part.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    part_number: int = Field(
        ge=1,
        description="Position of the part within the object.",
    )

    etag: str = Field(
        min_length=1,
        description="ETag returned when the part was uploaded.",
    )


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


def render_initiate_multipart_xml(
    bucket_name: str,
    object_key: str,
    upload_id: str,
) -> str:
    """
    Render an S3-compatible XML response for CreateMultipartUpload,
    carrying the upload id the client sends back with every part.
    """
    return "".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<InitiateMultipartUploadResult xmlns="{S3_XMLNS}">',
        f"<Bucket>{escape(bucket_name)}</Bucket>",
        f"<Key>{escape(object_key)}</Key>",
        f"<UploadId>{escape(upload_id)}</UploadId>",
        "</InitiateMultipartUploadResult>",
    ])


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
            etag=_normalize_etag(values.get("ETag", "")),
        )
    except (ValidationError, ValueError) as exc:
        raise ValueError("Malformed CompleteMultipartUpload.") from exc


def _normalize_etag(value: str) -> str:
    """Strip the quotes clients wrap around an ETag."""
    return value.strip().strip('"').lower()


def _local_name(tag: str) -> str:
    """Return an element name without its namespace prefix."""
    return tag.rsplit("}", 1)[-1]
