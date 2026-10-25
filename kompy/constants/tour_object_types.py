"""Formats a tour can be returned in by ``KomootConnector.get_tour_by_id``."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['TourObjectTypes']


class TourObjectTypes(KomootStrEnum):
    """Types of tour objects to be returned."""

    KOMPY = 'kompy'
    """A :class:`kompy.Tour` object."""
    GPX = 'gpx'
    """A ``gpxpy.gpx.GPX`` object."""
    FIT = 'fit'
    """A ``fit_tool.fit_file.FitFile`` object (planned tours only)."""
