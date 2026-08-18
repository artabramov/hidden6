# app/xml/parse_bucket_objekt_lock.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.etree import ElementTree


def parse_bucket_objekt_lock(
    body: bytes,
) -> tuple[str | None, str | None, int | None, int | None]:
    """
    Parse a PutObjectLockConfiguration request body.

    Returns ObjectLockEnabled, default retention mode, days, and years.
    Element namespaces are ignored.

    Raises:
        ValueError: Body is not a well formed ObjectLockConfiguration.
    """
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("Malformed ObjectLockConfiguration.") from exc

    if _strip_element(root.tag) != "ObjectLockConfiguration":
        raise ValueError("Malformed ObjectLockConfiguration.")

    objekt_lock_enabled = None
    default_lock_mode = None
    default_retention_days = None
    default_retention_years = None

    for element in root:
        name = _strip_element(element.tag)

        if name == "ObjectLockEnabled":
            if element.text:
                objekt_lock_enabled = element.text.strip()

        elif name == "Rule":
            (
                default_lock_mode,
                default_retention_days,
                default_retention_years,
            ) = _parse_rule(element)

    return (
        objekt_lock_enabled,
        default_lock_mode,
        default_retention_days,
        default_retention_years,
    )


def _parse_rule(
    rule: ElementTree.Element,
) -> tuple[str | None, int | None, int | None]:
    """Parse the default retention rule."""
    for element in rule:
        if _strip_element(element.tag) == "DefaultRetention":
            return _parse_default_retention(element)

    raise ValueError("Malformed ObjectLockConfiguration.")


def _parse_default_retention(
    retention: ElementTree.Element,
) -> tuple[str | None, int | None, int | None]:
    """Parse the default Object Lock retention configuration."""
    mode = None
    days = None
    years = None

    try:
        for element in retention:
            name = _strip_element(element.tag)

            if name == "Mode" and element.text:
                mode = element.text.strip()

            elif name == "Days" and element.text:
                days = int(element.text.strip())

            elif name == "Years" and element.text:
                years = int(element.text.strip())

    except ValueError as exc:
        raise ValueError("Malformed ObjectLockConfiguration.") from exc

    return mode, days, years


def _strip_element(tag: str) -> str:
    """Return an element name without its namespace prefix."""
    return tag.rsplit("}", 1)[-1]
