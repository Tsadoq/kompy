"""Segments of a planned tour."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kompy._parsing import coerce_enum, optional_str, require_int, require_str
from kompy.constants.segment_type import SegmentType

__all__ = ['AnnotatedSegment', 'Segment', 'SegmentInformation']


@dataclass
class SegmentInformation:
    """
    Boundaries of a stretch of a tour, as indices into the tour's coordinates.

    :param start_index_point: Index of the first coordinate of the stretch.
    :param end_index_point: Index of the last coordinate of the stretch.
    """

    start_index_point: int
    end_index_point: int

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build the boundaries from the API shape ``{"from": 0, "to": 19}``.

        :param data: A payload with ``from`` and ``to`` indices.
        :return: The parsed boundaries.
        :raises KeyError: If ``from`` or ``to`` is missing.
        """
        return cls(start_index_point=require_int(data, 'from'), end_index_point=require_int(data, 'to'))


@dataclass
class Segment:
    """
    A segment of a planned tour: the stretch between two consecutive waypoints.

    :param segment_type: How the segment was created, usually a :class:`kompy.constants.SegmentType`. Unknown
        types are kept as plain strings.
    :param segment_boundaries: Boundaries of the segment.
    :param reference: Reference of the segment (optional).
    """

    segment_type: SegmentType | str
    segment_boundaries: SegmentInformation
    reference: str | None = None

    def __post_init__(self) -> None:
        self.segment_type = coerce_enum(SegmentType, self.segment_type)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build a segment from the API shape ``{"type": "Routed", "from": 0, "to": 19, "reference"?: ...}``.

        :param data: One entry of a tour's ``segments``.
        :return: The parsed segment.
        :raises KeyError: If ``type``, ``from`` or ``to`` is missing.
        """
        return cls(
            segment_type=require_str(data, 'type'),
            segment_boundaries=SegmentInformation.from_dict(data),
            reference=optional_str(data.get('reference')),
        )


@dataclass
class AnnotatedSegment:
    """
    A stretch of a tour sharing one property, such as a way type or a surface.

    These come from the tour's embedded ``way_types`` and ``surfaces`` resources
    (see ``KomootConnector.get_tour_by_id(..., embedded=...)``).

    :param element: The shared property, e.g. ``'wt#way'`` (a :class:`kompy.constants.PossibleWayType`) or
        ``'sf#gravel'`` (a :class:`kompy.constants.SurfaceType`). Unknown values are plain strings.
    :param segment_boundaries: Boundaries of the stretch.
    """

    element: str
    segment_boundaries: SegmentInformation

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build the stretch from the API shape ``{"from": 0, "to": 33, "element": "wt#way"}``.

        :param data: One entry of an embedded ``way_types`` or ``surfaces`` resource.
        :return: The parsed stretch, with ``element`` kept as returned by the API.
        :raises KeyError: If a key is missing.
        """
        return cls(element=require_str(data, 'element'), segment_boundaries=SegmentInformation.from_dict(data))
