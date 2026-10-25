"""Tests for :class:`kompy.Waypoint`."""

from __future__ import annotations

import pytest

from kompy import Coordinate, Waypoint


def test_from_dict_minimal() -> None:
    waypoint = Waypoint.from_dict({'location': {'lat': 46.009014, 'lng': 8.000306}, 'index': 0})

    assert waypoint == Waypoint(location=Coordinate(46.009014, 8.000306), index=0)
    assert waypoint.end_index is None
    assert waypoint.reference is None


def test_from_dict_full() -> None:
    waypoint = Waypoint.from_dict(
        {'location': {'lat': 46.0, 'lng': 8.0}, 'index': 19, 'end_index': 33, 'reference': 'hl:85124'}
    )

    assert waypoint.end_index == 33
    assert waypoint.reference == 'hl:85124'


def test_from_dict_requires_location() -> None:
    with pytest.raises(KeyError):
        Waypoint.from_dict({'index': 0})
