"""
Constants of the Komoot API.

Enumerations are :class:`enum.StrEnum` subclasses: members are plain strings, so ``'hike'`` and
``SupportedActivities.HIKING`` can be used interchangeably.
"""

from __future__ import annotations

import warnings
from typing import Any

from kompy.constants.activities import SupportedActivities
from kompy.constants.difficulty_grade import DifficultyGrade
from kompy.constants.privacy_status import PrivacyStatus
from kompy.constants.query_parameters import TourQueryParameters
from kompy.constants.segment_type import SegmentType
from kompy.constants.surface import SurfaceType
from kompy.constants.tour_constants import (
    SmartTourTypes,
    TourSort,
    TourSortField,
    TourTypes,
)
from kompy.constants.tour_object_types import TourObjectTypes
from kompy.constants.way_type import PossibleWayType

__all__ = [
    'DifficultyGrade',
    'PossibleWayType',
    'PrivacyStatus',
    'SegmentType',
    'SmartTourTypes',
    'SupportedActivities',
    'SurfaceType',
    'TourObjectTypes',
    'TourQueryParameters',
    'TourSort',
    'TourSortField',
    'TourTypes',
]


def __getattr__(name: str) -> Any:
    """
    Resolve ``kompy.constants.Waypoint``, which moved to :mod:`kompy.waypoint`, with a deprecation warning.

    :param name: Name of the attribute being looked up.
    :return: The :class:`kompy.Waypoint` class.
    :raises AttributeError: For any other unknown attribute.
    """
    if name == 'Waypoint':
        from kompy.waypoint import Waypoint  # noqa: PLC0415 - imported lazily to avoid a circular import

        warnings.warn(
            'kompy.constants.Waypoint is deprecated; import Waypoint from kompy instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return Waypoint
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
