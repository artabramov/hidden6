# app/schemas/bucket_create.py
# SPDX-License-Identifier: GPL-3.0-only

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.validators.bucket_name import validate_bucket_name


class BucketCreateRequest(BaseModel):
    """
    Request schema for S3 CreateBucket. bucket_name comes from the
    path; this model owns naming validation for the operation.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    bucket_name: str = Field(
        min_length=3,
        max_length=63,
        description="S3 bucket name (DNS-compliant, globally unique).",
    )

    @field_validator("bucket_name")
    @classmethod
    def validate_bucket_name_field(cls, value: str) -> str:
        return validate_bucket_name(value)
