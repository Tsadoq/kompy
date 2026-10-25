"""Types of the segments a planned tour is made of."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['SegmentType']


class SegmentType(KomootStrEnum):
    """How a segment of a planned tour was created."""

    ROUTED = 'Routed'
    """The segment was computed by Komoot's router."""
    MANUAL = 'Manual'
    """The segment was drawn by hand (straight line, off grid)."""
