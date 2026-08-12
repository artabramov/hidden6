# app/schemas/multipart_complete.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field


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
