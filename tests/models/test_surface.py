"""Tests for :class:`kompy.Surface`."""

from __future__ import annotations

import pytest

from kompy import Surface
from kompy.constants import SurfaceType


def test_initialization_with_valid_inputs() -> None:
    surface = Surface(surface_type=SurfaceType.PAVING_STONES_BIKE, amount=0.5)

    assert surface.type == SurfaceType.PAVING_STONES_BIKE
    assert surface.amount == 0.5


def test_plain_string_type_becomes_enum_member() -> None:
    assert Surface('sf#asphalt', 0.1).type is SurfaceType.ASPHALT_FOOT


def test_unknown_surface_type_is_kept_as_plain_string() -> None:
    surface = Surface(surface_type='sf#ice', amount=0.5)

    assert surface.type == 'sf#ice'
    assert not isinstance(surface.type, SurfaceType)


@pytest.mark.parametrize('amount', [0, 1])
def test_boundary_amounts_are_accepted(amount: float) -> None:
    assert Surface(SurfaceType.GRAVEL_FOOT, amount).amount == amount


@pytest.mark.parametrize(('amount', 'expected'), [(1.0000001, 1.0), (-0.0000001, 0.0)])
def test_rounding_noise_is_clamped(amount: float, expected: float) -> None:
    assert Surface(SurfaceType.GRAVEL_FOOT, amount).amount == expected


@pytest.mark.parametrize('amount', [-0.1, 1.1])
def test_amount_out_of_range_is_rejected(amount: float) -> None:
    with pytest.raises(ValueError, match='between 0 and 1'):
        Surface(surface_type=SurfaceType.PAVING_STONES_BIKE, amount=amount)


def test_from_dict() -> None:
    surface = Surface.from_dict({'type': 'sf#unpaved', 'amount': 0.12239371})

    assert surface == Surface(SurfaceType.UNPAVED_FOOT, 0.12239371)


def test_from_dict_requires_keys() -> None:
    with pytest.raises(KeyError):
        Surface.from_dict({'type': 'sf#unpaved'})
