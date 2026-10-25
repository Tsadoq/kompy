"""Tests for :class:`kompy.Coordinate`."""

from __future__ import annotations

import pytest

from kompy import Coordinate


def test_valid_initialization() -> None:
    coord = Coordinate(30, 40, 500, 1000)

    assert (coord.lat, coord.lon, coord.alt, coord.time) == (30, 40, 500, 1000)


def test_keyword_initialization_without_optional_params() -> None:
    coord = Coordinate(lat=30, lon=40)

    assert coord.alt is None
    assert coord.time is None


@pytest.mark.parametrize(('lat', 'lon'), [(90, 180), (-90, -180), (0, 0)])
def test_boundary_values_are_accepted(lat: float, lon: float) -> None:
    coord = Coordinate(lat, lon)

    assert (coord.lat, coord.lon) == (lat, lon)


@pytest.mark.parametrize('lat', [91, -91, 90.0001])
def test_invalid_latitude(lat: float) -> None:
    with pytest.raises(ValueError, match='latitude'):
        Coordinate(lat, 40)


@pytest.mark.parametrize('lon', [181, -181])
def test_invalid_longitude(lon: float) -> None:
    with pytest.raises(ValueError, match='longitude'):
        Coordinate(30, lon)


def test_negative_time_is_rejected() -> None:
    with pytest.raises(ValueError, match='time'):
        Coordinate(30, 40, 500, -1)


def test_zero_time_is_accepted() -> None:
    assert Coordinate(30, 40, 500, 0).time == 0


@pytest.mark.parametrize('alt', [-10001, 10001, 25000])
def test_altitude_is_not_validated(alt: float) -> None:
    """Altitude is measured data; implausible readings must not make a tour unreadable."""
    assert Coordinate(30, 40, alt).alt == alt


def test_validate_alt_is_kept_for_backward_compatibility() -> None:
    Coordinate.validate_alt(alt=123456)


def test_equality_and_repr() -> None:
    assert Coordinate(1, 2, 3) == Coordinate(lat=1, lon=2, alt=3)
    assert Coordinate(1, 2) != Coordinate(1, 3)
    assert repr(Coordinate(1, 2)) == 'Coordinate(lat=1, lon=2, alt=None, time=None)'


def test_from_dict_full_payload() -> None:
    coord = Coordinate.from_dict({'lat': 46.002331, 'lng': 8.002309, 'alt': 578.4, 't': 2000, 'd': 0})

    assert coord == Coordinate(lat=46.002331, lon=8.002309, alt=578.4, time=2000.0)


def test_from_dict_without_optional_keys() -> None:
    coord = Coordinate.from_dict({'lat': 46.0, 'lng': 8.0})

    assert coord.alt is None
    assert coord.time is None


def test_from_dict_ignores_non_numeric_optional_values() -> None:
    coord = Coordinate.from_dict({'lat': 46.0, 'lng': 8.0, 'alt': None, 't': 'soon'})

    assert coord.alt is None
    assert coord.time is None


def test_from_dict_requires_lat_and_lng() -> None:
    with pytest.raises(KeyError):
        Coordinate.from_dict({'lat': 46.0, 'lon': 8.0})


def test_to_dict_round_trip() -> None:
    payload = {'lat': 46.0, 'lng': 8.0, 'alt': 500.0, 't': 1000.0}

    assert Coordinate.from_dict(payload).to_dict() == payload
    assert Coordinate(46.0, 8.0).to_dict() == {'lat': 46.0, 'lng': 8.0}
