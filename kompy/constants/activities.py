"""Sport types (activities) known to Komoot."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['SupportedActivities']


class SupportedActivities(KomootStrEnum):
    """
    Activities that are supported by Komoot.

    The up-to-date list is published at https://static.komoot.de/doc/external-api/v007/sports.html.
    Komoot adds sports over time: kompy accepts values missing from this enum as plain strings.
    """

    # Main sport types
    HIKING = 'hike'
    MOUNTAINEERING = 'mountaineering'
    MOUNTAINEERING_ADVANCED = 'mountaineering_advanced'
    ROAD_CYCLING = 'racebike'
    E_ROAD_CYCLING = 'e_racebike'
    BIKE_TOURING = 'touringbicycle'
    E_BIKE_TOURING = 'e_touringbicycle'
    MOUNTAIN_BIKING = 'mtb'
    E_MOUNTAIN_BIKING = 'e_mtb'
    GRAVEL_RIDING = 'mtb_easy'
    E_GRAVEL_RIDING = 'e_mtb_easy'
    ENDURO_MTB = 'mtb_advanced'
    E_ENDURO_MTB = 'e_mtb_advanced'
    RUNNING = 'jogging'

    # Tracking sport types
    CLIMBING = 'climbing'
    DOWNHILL = 'downhillbike'
    CROSS_COUNTRY_SKIING = 'nordic'
    NORDIC_WALKING = 'nordicwalking'
    SKATING = 'skaten'
    ALPINE_SKIING = 'skialpin'
    ALPINE_SKI_TOURING = 'skitour'
    SLEDDING = 'sled'
    SNOWBOARDING = 'snowboard'
    SNOW_SHOE = 'snowshoe'
    UNICYCLING = 'unicycle'
    BIKE = 'citybike'
    OTHER = 'other'
