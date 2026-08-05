# app/schemas/pydantic_error.py
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

from pydantic import BaseModel, Field


class PydanticErrorDetail(BaseModel):
    """
    Single item in a 422 validation error response.

    Mirrors the shape produced by Pydantic / FastAPI request
    validation. Declared explicitly so Swagger documents a clear
    error structure rather than relying on the default 422 schema.
    """

    type: str = Field(
        description=(
            "Project-defined error type "
            "(e.g. value_invalid, value_not_found)."
        )
    )

    loc: list[str | int] = Field(
        description=(
            "Location of the invalid value "
            "(e.g. ['body', 'field_name'])."
        )
    )

    msg: str = Field(
        description="Human-readable validation error message."
    )

    input: Any | None = Field(
        default=None,
        description="Original input value that caused the error.",
    )


class PydanticErrorResponse(BaseModel):
    """
    Schema for project-level 422 responses. Contains a list of
    PydanticErrorDetail items describing one or more validation or
    value-related errors.
    """

    detail: list[PydanticErrorDetail]
