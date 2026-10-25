"""Waypoints of a planned tour."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kompy._parsing import optional_int, optional_str, require_int
from kompy.coordinate import Coordinate

__all__ = ['Waypoint']


@dataclass
class Waypoint:
    """
    A waypoint of a planned tour (an entry of the tour's ``path``).

    :param location: Location of the waypoint.
    :param index: Index into the tour coordinates array representing the location of the waypoint.
    :param end_index: Exclusive end index into the tour coordinates array, for waypoints spanning a stretch
        (optional).
    :param reference: Reference to a highlight or OSM POI (optional), e.g. ``'hl:85124'``.
    """

    location: Coordinate
    index: int
    end_index: int | None = None
    reference: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build a waypoint from the API shape ``{"location": {"lat", "lng"}, "index", "end_index"?, "reference"?}``.

        :param data: One entry of a tour's ``path``.
        :return: The parsed waypoint.
        :raises KeyError: If ``location`` or ``index`` is missing.
        """
        return cls(
            location=Coordinate.from_dict(data['location']),
            index=require_int(data, 'index'),
            end_index=optional_int(data.get('end_index')),
            reference=optional_str(data.get('reference')),
        )
