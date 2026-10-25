"""Tests for :class:`kompy.Highlight`."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from kompy import Coordinate, Highlight, KomootImage, User
from kompy.constants import SupportedActivities


def test_from_highlight_payload(api_fixture: Callable[[str], Any]) -> None:
    payload = api_fixture('highlight')

    highlight = Highlight.from_dict(payload)

    assert highlight.id == 85124
    assert highlight.type == 'highlight_segment'
    assert highlight.name == 'Sample name'
    assert highlight.sport is SupportedActivities.BIKE_TOURING
    assert highlight.start_point == Coordinate(46.001209, 8.003327, 74)
    assert highlight.mid_point == Coordinate(46.007215, 8.007112, 79)
    assert highlight.end_point == Coordinate(46.009364, 8.004221, 74)
    assert highlight.distance == 841
    assert highlight.elevation_up == 14
    assert highlight.elevation_down == 14
    assert isinstance(highlight.front_image, KomootImage)
    assert highlight.front_image.client_hash is not None
    assert highlight.front_image.templated is True
    assert isinstance(highlight.creator, User)
    assert highlight.creator.username == 'jan'
    assert highlight.creator.is_premium is True
    assert highlight.raw == payload
    assert highlight.url == 'https://www.komoot.com/highlight/85124'


def test_from_user_highlights_items(api_fixture: Callable[[str], Any]) -> None:
    items = api_fixture('user_highlights')['_embedded']['items']

    highlights = [Highlight.from_dict(item) for item in items]

    assert [h.id for h in highlights] == [item['id'] for item in items]
    for highlight in highlights:
        assert highlight.front_image is not None
        assert highlight.mid_point is not None


def test_minimal_payload() -> None:
    highlight = Highlight.from_dict({'id': 1, 'type': 'highlight_point', 'sport': 'paragliding'})

    assert highlight.sport == 'paragliding'
    assert highlight.start_point is None
    assert highlight.front_image is None
    assert highlight.creator is None
    assert highlight.distance is None


def test_malformed_optional_values_become_none() -> None:
    highlight = Highlight.from_dict({'id': '7', 'start_point': {'lat': 999, 'lng': 8}, '_embedded': 'junk'})

    assert highlight.id == 7
    assert highlight.start_point is None
    assert highlight.front_image is None


def test_id_is_required() -> None:
    with pytest.raises(KeyError):
        Highlight.from_dict({'name': 'No id'})
