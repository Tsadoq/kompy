"""Tests for :class:`kompy.WayType`."""

from __future__ import annotations

import pytest

from kompy import WayType
from kompy.constants import PossibleWayType


@pytest.mark.parametrize('way_type', PossibleWayType.list_all())
def test_every_known_way_type_is_accepted(way_type: str) -> None:
    instance = WayType(way_type, 0.5)

    assert instance.type == way_type
    assert isinstance(instance.type, PossibleWayType)
    assert instance.amount == 0.5


def test_unknown_way_type_is_kept_as_plain_string() -> None:
    instance = WayType(way_type='wt#via_ferrata', amount=0.5)

    assert instance.type == 'wt#via_ferrata'


@pytest.mark.parametrize('amount', [0, 1])
def test_boundary_amounts_are_accepted(amount: float) -> None:
    assert WayType(PossibleWayType.TRACK, amount).amount == amount


def test_rounding_noise_is_clamped() -> None:
    assert WayType(PossibleWayType.TRACK, 1.0000001).amount == 1.0


@pytest.mark.parametrize('amount', [-1, 2])
def test_amount_out_of_range_is_rejected(amount: float) -> None:
    with pytest.raises(ValueError, match='between 0 and 1'):
        WayType(PossibleWayType.TRACK, amount)


def test_from_dict() -> None:
    assert WayType.from_dict({'type': 'wt#street', 'amount': 0.25}) == WayType(PossibleWayType.STREET, 0.25)
