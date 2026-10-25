"""Tests for the private lenient-parsing helpers in :mod:`kompy._parsing`."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from kompy import _parsing
from kompy.constants import SupportedActivities


def test_coerce_enum_known_value() -> None:
    assert _parsing.coerce_enum(SupportedActivities, 'hike') is SupportedActivities.HIKING


def test_coerce_enum_unknown_value_is_logged_at_debug(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger='kompy'):
        value = _parsing.coerce_enum(SupportedActivities, 'hoverboard')

    assert value == 'hoverboard'
    assert type(value) is str
    assert [record.levelno for record in caplog.records] == [logging.DEBUG]
    assert 'hoverboard' in caplog.text


def test_coerce_optional_enum() -> None:
    assert _parsing.coerce_optional_enum(SupportedActivities, None) is None
    assert _parsing.coerce_optional_enum(SupportedActivities, 'mtb') is SupportedActivities.MOUNTAIN_BIKING


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('2026-10-24T12:46:45.000Z', datetime(2026, 10, 24, 12, 46, 45, tzinfo=UTC)),
        ('2026-10-24T12:46:45+00:00', datetime(2026, 10, 24, 12, 46, 45, tzinfo=UTC)),
        ('not a date', None),
        (None, None),
        (1700000000, None),
    ],
)
def test_parse_datetime(value: Any, expected: datetime | None) -> None:
    assert _parsing.parse_datetime(value) == expected


def _double(data: Mapping[str, Any]) -> int:
    return int(data['value']) * 2


def test_parse_optional() -> None:
    assert _parsing.parse_optional({'value': 2}, _double) == 4
    assert _parsing.parse_optional(None, _double) is None
    assert _parsing.parse_optional('not a mapping', _double) is None
    assert _parsing.parse_optional({}, _double) is None
    assert _parsing.parse_optional({'value': 'x'}, _double) is None


def test_parse_list_skips_malformed_entries() -> None:
    items = [{'value': 1}, {}, 'junk', {'value': 3}]

    assert _parsing.parse_list(items, _double) == [2, 6]


@pytest.mark.parametrize('items', [None, 'string', {'value': 1}, 42])
def test_parse_list_rejects_non_lists(items: Any) -> None:
    assert _parsing.parse_list(items, _double) == []


def test_parse_list_or_none() -> None:
    assert _parsing.parse_list_or_none(None, _double) is None
    assert _parsing.parse_list_or_none([{'value': 1}], _double) == [2]


@pytest.mark.parametrize(
    ('value', 'as_float', 'as_int'),
    [(3, 3.0, 3), (2.7, 2.7, 2), (None, None, None), ('3', None, None), (True, None, None)],
)
def test_optional_numbers(value: Any, as_float: float | None, as_int: int | None) -> None:
    assert _parsing.optional_float(value) == as_float
    assert _parsing.optional_int(value) == as_int


def test_optional_str_and_bool() -> None:
    assert _parsing.optional_str('a') == 'a'
    assert _parsing.optional_str(1) is None
    assert _parsing.optional_bool(False) is False
    assert _parsing.optional_bool('false') is None


def test_link_href() -> None:
    links = {'coordinates': {'href': 'https://example.com/c'}, 'broken': 'x'}

    assert _parsing.link_href(links, 'coordinates') == 'https://example.com/c'
    assert _parsing.link_href(links, 'missing') is None
    assert _parsing.link_href(links, 'broken') is None
    assert _parsing.link_href(None, 'coordinates') is None


# ----------------------------------------------------------------- required values


@pytest.mark.parametrize(('value', 'expected'), [('jane', 'jane'), (12345, '12345')])
def test_require_str_accepts_strings_and_integers(value: object, expected: str) -> None:
    assert _parsing.require_str({'key': value}, 'key') == expected


@pytest.mark.parametrize(
    ('data', 'error'),
    [
        ({}, KeyError),
        ({'key': None}, TypeError),
        ({'key': True}, TypeError),
        ({'key': 1.5}, TypeError),
        ({'key': ''}, ValueError),
    ],
)
def test_require_str_rejects_null_and_other_types(data: dict[str, Any], error: type[Exception]) -> None:
    with pytest.raises(error):
        _parsing.require_str(data, 'key')


@pytest.mark.parametrize(('value', 'expected'), [(12, 12), (12.0, 12), ('12', 12)])
def test_require_int_accepts_whole_numbers(value: object, expected: int) -> None:
    assert _parsing.require_int({'key': value}, 'key') == expected


@pytest.mark.parametrize(
    ('data', 'error'),
    [
        ({}, KeyError),
        ({'key': None}, TypeError),
        ({'key': True}, TypeError),
        ({'key': 12.7}, ValueError),
        ({'key': 'abc'}, ValueError),
        ({'key': [1]}, TypeError),
    ],
)
def test_require_int_rejects_booleans_fractions_and_garbage(data: dict[str, Any], error: type[Exception]) -> None:
    with pytest.raises(error):
        _parsing.require_int(data, 'key')
