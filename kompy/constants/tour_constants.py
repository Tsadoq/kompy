"""Enumerations used to describe, filter and sort tours."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['SmartTourTypes', 'TourSort', 'TourSortField', 'TourTypes']


class TourTypes(KomootStrEnum):
    """Types of tour."""

    TOUR_PLANNED = 'tour_planned'
    TOUR_RECORDED = 'tour_recorded'


class SmartTourTypes(KomootStrEnum):
    """Types of smart tour. Only reported by the API for smart tours in format v2."""

    SMART_TOUR_PLAIN = 'SMART_TOUR_PLAIN'
    SMART_TOUR_CUSTOMIZED = 'SMART_TOUR_CUSTOMIZED'


class TourSort(KomootStrEnum):
    """Sort direction of the tour list."""

    ASCENDING = 'asc'
    DESCENDING = 'desc'


class TourSortField(KomootStrEnum):
    """Field to sort the tour list by."""

    NAME = 'name'
    ELEVATION = 'elevation'
    DURATION = 'duration'
    DATE = 'date'
    PROXIMITY = 'proximity'
