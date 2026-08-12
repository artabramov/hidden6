# app/schemas/objekt_upload.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.constants import OBJEKT_KEY_MAX_BYTES
from app.validators.object_key import validate_object_key


class ObjektUploadRequest(BaseModel):
    """
    Request schema for S3 PutObject. object_key comes from the path;
    this model owns key validation for the operation.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    object_key: str = Field(
        min_length=1,
        max_length=OBJEKT_KEY_MAX_BYTES,
        description="S3 object key relative to the bucket root.",
    )

    @field_validator("object_key")
    @classmethod
    def validate_object_key_field(cls, value: str) -> str:
        return validate_object_key(value)
