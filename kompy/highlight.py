"""Komoot highlights: places and stretches recommended by the community."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Self

from kompy._parsing import coerce_optional_enum, optional_float, optional_str, parse_optional, require_int
from kompy.constants.activities import SupportedActivities
from kompy.coordinate import Coordinate
from kompy.image import KomootImage
from kompy.user import User

__all__ = ['Highlight']


@dataclass
class Highlight:
    """
    A Komoot highlight.

    A highlight is either a point (``type == 'highlight_point'``, e.g. a viewpoint) or a stretch of way
    (``type == 'highlight_segment'``, e.g. a scenic road). Fields the API does not return for a highlight are
    ``None``.

    :param id: Unique identifier of the highlight.
    :param type: ``'highlight_point'`` or ``'highlight_segment'``.
    :param name: Name of the highlight.
    :param sport: Sport the highlight was recommended for, usually a :class:`kompy.constants.SupportedActivities`.
    :param start_point: Start of a segment highlight.
    :param mid_point: Middle of a segment highlight, or the location of a point highlight.
    :param end_point: End of a segment highlight.
    :param distance: Length of a segment highlight, in meters.
    :param elevation_up: Elevation gain along a segment highlight, in meters.
    :param elevation_down: Elevation loss along a segment highlight, in meters.
    :param front_image: The highlight's cover picture.
    :param creator: The user who created the highlight.
    :param raw: The payload the highlight was parsed from.
    """

    id: int
    type: str | None = None
    name: str | None = None
    sport: SupportedActivities | str | None = None
    start_point: Coordinate | None = None
    mid_point: Coordinate | None = None
    end_point: Coordinate | None = None
    distance: float | None = None
    elevation_up: float | None = None
    elevation_down: float | None = None
    front_image: KomootImage | None = None
    creator: User | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build a highlight from the API payload (``/highlights/{id}`` or an item of a user's highlights).

        :param data: The highlight payload.
        :return: The parsed highlight.
        :raises KeyError: If ``id`` is missing.
        :raises ValueError: If ``id`` is not an integer.
        """
        embedded = data.get('_embedded')
        if not isinstance(embedded, Mapping):
            embedded = {}
        return cls(
            id=require_int(data, 'id'),
            type=optional_str(data.get('type')),
            name=optional_str(data.get('name')),
            sport=coerce_optional_enum(SupportedActivities, data.get('sport')),
            start_point=parse_optional(data.get('start_point'), Coordinate.from_dict),
            mid_point=parse_optional(data.get('mid_point'), Coordinate.from_dict),
            end_point=parse_optional(data.get('end_point'), Coordinate.from_dict),
            distance=optional_float(data.get('distance')),
            elevation_up=optional_float(data.get('elevation_up')),
            elevation_down=optional_float(data.get('elevation_down')),
            front_image=parse_optional(embedded.get('front_image'), KomootImage.from_dict),
            creator=parse_optional(embedded.get('creator'), User.from_dict),
            raw=dict(data),
        )

    @property
    def url(self) -> str:
        """Link to the highlight on komoot.com."""
        return f'https://www.komoot.com/highlight/{self.id}'
