"""Way types Komoot uses in tour summaries and way type segments."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['PossibleWayType']


class PossibleWayType(KomootStrEnum):
    """
    Way types of a tour.

    The complete list can be found at https://static.komoot.de/doc/external-api/v007/waytypes.html.
    Komoot adds values over time: kompy accepts values missing from this enum as plain strings.
    """

    FERRY = 'wt#ferry'
    ALPINE_BIKE_D9 = 'wt#alpine_bike_d9'
    ALPINE_BIKE_D8 = 'wt#alpine_bike_d8'
    ALPINE_BIKE = 'wt#alpine_bike'
    TRAIL_D7 = 'wt#trail_d7'
    TRAIL_D6 = 'wt#trail_d6'
    TRAIL_D5 = 'wt#trail_d5'
    TRAIL_D4 = 'wt#trail_d4'
    TRAIL_D3 = 'wt#trail_d3'
    TRAIL_D2 = 'wt#trail_d2'
    TRAIL_D1 = 'wt#trail_d1'
    TRAIL = 'wt#trail'
    HIKE_D9 = 'wt#hike_d9'
    HIKE_D8 = 'wt#hike_d8'
    HIKE_D7 = 'wt#hike_d7'
    HIKE_D6 = 'wt#hike_d6'
    HIKE_D5 = 'wt#hike_d5'
    HIKE_D4 = 'wt#hike_d4'
    HIKE_D3 = 'wt#hike_d3'
    HIKE_D2 = 'wt#hike_d2'
    HIKING_PATH = 'wt#hiking_path'
    LONG_HIKING_PATH = 'wt#long_hiking_path'
    ALPINE_HIKING_PATH = 'wt#alpine_hiking_path'
    MOUNTAIN_HIKING_PATH = 'wt#mountain_hiking_path'
    TRACK = 'wt#track'
    WAY = 'wt#way'
    MINOR_ROAD = 'wt#minor_road'
    STREET = 'wt#street'
    PRIMARY = 'wt#primary'
    SERVICE = 'wt#service'
    CYCLEWAY = 'wt#cycleway'
    CYCLE_ROUTE = 'wt#cycle_route'
    FOOTWAY = 'wt#footway'
    MOVABLE_BRIDGE = 'wt#movable_bridge'
    UNKNOWN = 'wt#unknown'
    OFF_GRID = 'wt#off_grid'
