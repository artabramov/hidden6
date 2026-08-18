# app/xml/parse_bucket_object_lock.py
# SPDX-License-Identifier: GPL-3.0-only

from xml.etree import ElementTree


def parse_bucket_object_lock(
    body: bytes,
) -> tuple[str | None, str | None, int | None, int | None]:
    """
    Parse and validate an S3 ObjectLockConfiguration request body.

    Returns ObjectLockEnabled, default retention mode, days, and years.
    Element namespaces are ignored.

    Raises:
        ValueError: Body does not match the expected
            ObjectLockConfiguration structure.
    """
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("Malformed ObjectLockConfiguration.") from exc

    if _strip_element(root.tag) != "ObjectLockConfiguration":
        raise ValueError("Malformed ObjectLockConfiguration.")

    object_lock_enabled = None
    default_lock_mode = None
    default_retention_days = None
    default_retention_years = None

    for element in root:
        name = _strip_element(element.tag)

        if name == "ObjectLockEnabled":
            if not element.text:
                raise ValueError("Malformed ObjectLockConfiguration.")

            object_lock_enabled = element.text.strip()

            if object_lock_enabled != "Enabled":
                raise ValueError("Malformed ObjectLockConfiguration.")

        elif name == "Rule":
            (
                default_lock_mode,
                default_retention_days,
                default_retention_years,
            ) = _parse_rule(element)

        else:
            raise ValueError("Malformed ObjectLockConfiguration.")

    return (
        object_lock_enabled,
        default_lock_mode,
        default_retention_days,
        default_retention_years,
    )


def _parse_rule(
    rule: ElementTree.Element,
) -> tuple[str, int | None, int | None]:
    """Parse and validate the default Object Lock retention rule."""
    children = list(rule)

    if (
        len(children) != 1
        or _strip_element(children[0].tag) != "DefaultRetention"
    ):
        raise ValueError("Malformed ObjectLockConfiguration.")

    return _parse_default_retention(children[0])


def _parse_default_retention(
    retention: ElementTree.Element,
) -> tuple[str, int | None, int | None]:
    """Parse and validate DefaultRetention."""
    mode = None
    days = None
    years = None

    for element in retention:
        name = _strip_element(element.tag)

        if name == "Mode":
            if not element.text:
                raise ValueError("Malformed ObjectLockConfiguration.")

            mode = element.text.strip()

            if mode not in ("GOVERNANCE", "COMPLIANCE"):
                raise ValueError("Malformed ObjectLockConfiguration.")

        elif name == "Days":
            if not element.text:
                raise ValueError("Malformed ObjectLockConfiguration.")

            try:
                days = int(element.text.strip())
            except ValueError as exc:
                raise ValueError(
                    "Malformed ObjectLockConfiguration."
                ) from exc

        elif name == "Years":
            if not element.text:
                raise ValueError("Malformed ObjectLockConfiguration.")

            try:
                years = int(element.text.strip())
            except ValueError as exc:
                raise ValueError(
                    "Malformed ObjectLockConfiguration."
                ) from exc

        else:
            raise ValueError("Malformed ObjectLockConfiguration.")

    if mode is None:
        raise ValueError("Malformed ObjectLockConfiguration.")

    if (days is None) == (years is None):
        raise ValueError("Malformed ObjectLockConfiguration.")

    if days is not None and days <= 0:
        raise ValueError("Malformed ObjectLockConfiguration.")

    if years is not None and years <= 0:
        raise ValueError("Malformed ObjectLockConfiguration.")

    return mode, days, years


def _strip_element(tag: str) -> str:
    """Return an element name without its namespace prefix."""
    return tag.rsplit("}", 1)[-1]
