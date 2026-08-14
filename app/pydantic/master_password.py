# app/pydantic/master_password.py
# SPDX-License-Identifier: GPL-3.0-only


def validate_master_password(value: str) -> str:
    if not any(c.islower() for c in value):
        raise ValueError(
            "Master password must contain a lowercase letter."
        )
    if not any(c.isupper() for c in value):
        raise ValueError(
            "Master password must contain an uppercase letter."
        )
    if not any(c.isdigit() for c in value):
        raise ValueError(
            "Master password must contain a digit."
        )
    return value
