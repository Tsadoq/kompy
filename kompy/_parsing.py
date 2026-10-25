"""
Private helpers that turn loosely structured API payloads into kompy models.

The Komoot API is unofficial and changes over time, so parsing is lenient: unknown enumeration values are kept as
plain strings and malformed optional values become ``None`` instead of failing the whole object.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

E = TypeVar('E', bound=StrEnum)
T = TypeVar('T')


def coerce_enum(enum_cls: type[E], value: str) -> E | str:
    """
    Convert a string to a member of ``enum_cls``, keeping unknown values as plain strings.

    :param enum_cls: The enumeration the value is expected to belong to.
    :param value: The raw value returned by the API.
    :return: The matching enum member, or ``value`` unchanged when it is not a known member.
    """
    try:
        return enum_cls(value)
    except ValueError:
        logger.debug('Unknown %s value %r; keeping it as a plain string.', enum_cls.__name__, value)
        return value


def coerce_optional_enum(enum_cls: type[E], value: Any) -> E | str | None:
    """
    Like :func:`coerce_enum`, but map ``None`` (a missing or ``null`` value) to ``None``.

    :param enum_cls: The enumeration the value is expected to belong to.
    :param value: The raw value returned by the API, possibly ``None``.
    :return: The matching enum member, the raw string, or ``None``.
    """
    if value is None:
        return None
    return coerce_enum(enum_cls, str(value))


def parse_datetime(value: Any) -> datetime | None:
    """
    Parse an ISO 8601 timestamp such as ``2026-10-24T12:46:45.000Z``.

    :param value: The raw value returned by the API.
    :return: A timezone-aware datetime, or ``None`` when the value is missing or not a valid timestamp.
    """
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.debug('Could not parse timestamp %r.', value)
        return None


def parse_optional(data: Any, parser: Callable[[Mapping[str, Any]], T]) -> T | None:
    """
    Parse an optional nested object, returning ``None`` when it is absent or malformed.

    :param data: The nested object, usually ``payload.get('key')``.
    :param parser: Function building the model from a mapping, typically a ``from_dict`` classmethod.
    :return: The parsed model, or ``None``.
    """
    if not isinstance(data, Mapping):
        return None
    try:
        return parser(data)
    except (KeyError, TypeError, ValueError) as error:
        logger.debug('Skipping malformed %s payload: %r', getattr(parser, '__qualname__', parser), error)
        return None


def parse_list(items: Any, parser: Callable[[Mapping[str, Any]], T]) -> list[T]:
    """
    Parse a list of nested objects, skipping (and logging) the entries that are malformed.

    :param items: The raw list returned by the API; anything that is not a list yields an empty list.
    :param parser: Function building one model from a mapping, typically a ``from_dict`` classmethod.
    :return: The successfully parsed models, in their original order.
    """
    if not isinstance(items, Iterable) or isinstance(items, str | bytes | Mapping):
        return []
    parsed = (parse_optional(item, parser) for item in items)
    return [item for item in parsed if item is not None]


def parse_list_or_none(items: Any, parser: Callable[[Mapping[str, Any]], T]) -> list[T] | None:
    """
    Like :func:`parse_list`, but return ``None`` when the list itself is missing (``None``).

    :param items: The raw list returned by the API, or ``None``.
    :param parser: Function building one model from a mapping, typically a ``from_dict`` classmethod.
    :return: The successfully parsed models, or ``None``.
    """
    return None if items is None else parse_list(items, parser)


def require_str(data: Mapping[str, Any], key: str) -> str:
    """
    Read a required text value, such as a username or an image URL.

    Unlike ``str(data[key])``, a JSON ``null`` does not become the string ``'None'``: it is rejected, so the
    enclosing object is skipped (or becomes ``None``) through :func:`parse_optional` and :func:`parse_list`.

    :param data: The payload.
    :param key: The key of the value.
    :return: The value; an integer (e.g. a numeric username) is converted to a string.
    :raises KeyError: If the key is missing.
    :raises TypeError: If the value is neither a string nor an integer.
    :raises ValueError: If the value is an empty string.
    """
    value = data[key]
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str):
        raise TypeError(f'{key!r} must be a string, got {value!r}.')
    if not value:
        raise ValueError(f'{key!r} must not be empty.')
    return value


def require_int(data: Mapping[str, Any], key: str) -> int:
    """
    Read a required integer, such as an id.

    Unlike ``int(data[key])``, booleans and fractional numbers are rejected instead of being truncated.

    :param data: The payload.
    :param key: The key of the value.
    :return: The value; a whole float (``12.0``) or a string of digits (``'12'``) is converted.
    :raises KeyError: If the key is missing.
    :raises TypeError: If the value is not a number or a string.
    :raises ValueError: If the value is not a whole number.
    """
    value = data[key]
    if isinstance(value, bool):
        raise TypeError(f'{key!r} must be an integer, got {value!r}.')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f'{key!r} must be a whole number, got {value!r}.')
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f'{key!r} must be an integer, got {value!r}.')


def optional_float(value: Any) -> float | None:
    """
    Convert a numeric API value to ``float``.

    :param value: The raw value returned by the API.
    :return: The value as a float, or ``None`` when it is missing or not numeric.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def optional_int(value: Any) -> int | None:
    """
    Convert an integral API value to ``int``.

    :param value: The raw value returned by the API.
    :return: The value as an int, or ``None`` when it is missing or not numeric.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return int(value)


def optional_str(value: Any) -> str | None:
    """
    Return ``value`` when it is a string.

    :param value: The raw value returned by the API.
    :return: The string, or ``None`` for any other type.
    """
    return value if isinstance(value, str) else None


def optional_bool(value: Any) -> bool | None:
    """
    Return ``value`` when it is a boolean.

    :param value: The raw value returned by the API.
    :return: The boolean, or ``None`` for any other type.
    """
    return value if isinstance(value, bool) else None


def link_href(links: Any, name: str) -> str | None:
    """
    Read ``_links[name].href`` from a HAL payload.

    :param links: The ``_links`` object of the payload (may be missing).
    :param name: Name of the link relation.
    :return: The link target, or ``None`` when absent.
    """
    if not isinstance(links, Mapping):
        return None
    link = links.get(name)
    if not isinstance(link, Mapping):
        return None
    return optional_str(link.get('href'))
