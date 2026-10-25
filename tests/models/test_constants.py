"""Tests for the enumerations in :mod:`kompy.constants`."""

from __future__ import annotations

import json
from enum import StrEnum

import pytest

import kompy
from kompy import constants
from kompy.constants import (
    DifficultyGrade,
    PossibleWayType,
    PrivacyStatus,
    SegmentType,
    SmartTourTypes,
    SupportedActivities,
    SurfaceType,
    TourObjectTypes,
    TourSort,
    TourSortField,
    TourTypes,
)

ALL_ENUMS = [
    DifficultyGrade,
    PossibleWayType,
    PrivacyStatus,
    SegmentType,
    SmartTourTypes,
    SupportedActivities,
    SurfaceType,
    TourObjectTypes,
    TourSort,
    TourSortField,
    TourTypes,
]


@pytest.mark.parametrize('enum_cls', ALL_ENUMS)
def test_constants_are_str_enums(enum_cls: type[StrEnum]) -> None:
    assert issubclass(enum_cls, StrEnum)
    for member in enum_cls:
        assert member == member.value
        assert str(member) == member.value
        assert f'{member}' == member.value


@pytest.mark.parametrize('enum_cls', ALL_ENUMS)
def test_list_all_returns_plain_strings_in_declaration_order(enum_cls: type[constants.SupportedActivities]) -> None:
    values = enum_cls.list_all()

    assert values == [member.value for member in enum_cls]
    assert all(type(value) is str for value in values)


def test_list_all_order_matches_declaration() -> None:
    assert SupportedActivities.list_all()[:2] == ['hike', 'mountaineering']
    assert DifficultyGrade.list_all() == ['easy', 'moderate', 'difficult']
    assert TourSort.list_all() == ['asc', 'desc']
    assert PrivacyStatus.list_all() == ['public', 'private', 'friends']


@pytest.mark.parametrize(
    ('member', 'value'),
    [
        (SupportedActivities.HIKING, 'hike'),
        (SupportedActivities.RUNNING, 'jogging'),
        (SupportedActivities.ROAD_CYCLING, 'racebike'),
        (DifficultyGrade.MODERATE, 'moderate'),
        (PrivacyStatus.FRIENDS, 'friends'),
        (SegmentType.ROUTED, 'Routed'),
        (SurfaceType.ASPHALT_BIKE, 'sb#asphalt'),
        (PossibleWayType.OFF_GRID, 'wt#off_grid'),
        (TourTypes.TOUR_RECORDED, 'tour_recorded'),
        (SmartTourTypes.SMART_TOUR_PLAIN, 'SMART_TOUR_PLAIN'),
        (TourSortField.PROXIMITY, 'proximity'),
        (TourObjectTypes.FIT, 'fit'),
    ],
)
def test_values_are_unchanged(member: StrEnum, value: str) -> None:
    assert member == value


def test_member_counts_are_unchanged() -> None:
    assert len(SupportedActivities) == 27
    assert len(SurfaceType) == 48
    assert len(PossibleWayType) == 36


@pytest.mark.parametrize(
    'sport',
    [
        'jogging',
        'hike',
        'other',
        'racebike',
        'skialpin',
        'touringbicycle',
        'mtb',
        'snowshoe',
        'mountaineering',
        'nordic',
    ],
)
def test_sports_seen_on_the_live_api_are_known(sport: str) -> None:
    assert sport in SupportedActivities.list_all()


def test_members_serialize_as_plain_strings() -> None:
    assert json.dumps({'sport': SupportedActivities.HIKING}) == '{"sport": "hike"}'


def test_plain_strings_look_up_members() -> None:
    assert SupportedActivities('hike') is SupportedActivities.HIKING
    assert 'hike' in SupportedActivities.list_all()


def test_constants_are_reexported_from_the_package() -> None:
    assert kompy.SupportedActivities is SupportedActivities
    assert kompy.constants.TourQueryParameters is constants.TourQueryParameters


def test_waypoint_from_constants_package_is_deprecated() -> None:
    with pytest.warns(DeprecationWarning, match=r'kompy\.constants\.Waypoint is deprecated'):
        from kompy.constants import Waypoint

    assert Waypoint is kompy.Waypoint


def test_waypoint_from_constants_module_is_deprecated() -> None:
    with pytest.warns(DeprecationWarning, match=r'kompy\.constants\.waypoint\.Waypoint is deprecated'):
        from kompy.constants.waypoint import Waypoint

    assert Waypoint is kompy.Waypoint


@pytest.mark.parametrize('module_name', ['kompy.constants', 'kompy.constants.waypoint'])
def test_unknown_attributes_still_raise(module_name: str) -> None:
    import importlib

    module = importlib.import_module(module_name)

    with pytest.raises(AttributeError, match='Nope'):
        _ = module.Nope
