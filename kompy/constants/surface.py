"""Surface types Komoot uses in tour summaries and surface segments."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['SurfaceType']


class SurfaceType(KomootStrEnum):
    """
    Surface types of a tour.

    The complete list can be found at https://static.komoot.de/doc/external-api/v007/surfaces.html.
    Komoot adds values over time: kompy accepts values missing from this enum as plain strings.
    """

    # Bike
    ASPHALT_BIKE = 'sb#asphalt'
    CONCRETE_BIKE = 'sb#concrete'
    PAVED_BIKE = 'sb#paved'
    PAVING_STONES_BIKE = 'sb#paving_stones'
    COBBLESTONE_BIKE = 'sb#cobblestone'
    COBBLES_BIKE = 'sb#cobbles'
    COMPACTED_BIKE = 'sb#compacted'
    GRAVEL_BIKE = 'sb#gravel'
    GRASS_PAVER_BIKE = 'sb#grass_paver'
    WOOD_BIKE = 'sb#wood'
    SAND_BIKE = 'sb#sand'
    GROUND_BIKE = 'sb#ground'
    STONE_BIKE = 'sb#stone'
    UNPAVED_BIKE = 'sb#unpaved'
    ALPIN_BIKE = 'sb#alpin'
    UNKNOWN_BIKE = 'sb#unknown'

    # Foot
    ASPHALT_FOOT = 'sf#asphalt'
    CONCRETE_FOOT = 'sf#concrete'
    COBBLESTONE_FOOT = 'sf#cobblestone'
    PAVING_STONES_FOOT = 'sf#paving_stones'
    PAVED_FOOT = 'sf#paved'
    COMPACTED_FOOT = 'sf#compacted'
    GRAVEL_FOOT = 'sf#gravel'
    GRASS_PAVER_FOOT = 'sf#grass_paver'
    WOOD_FOOT = 'sf#wood'
    UNPAVED_FOOT = 'sf#unpaved'
    SAND_FOOT = 'sf#sand'
    GROUND_FOOT = 'sf#ground'
    STONE_FOOT = 'sf#stone'
    NATURE_FOOT = 'sf#nature'
    ALPIN_FOOT = 'sf#alpin'
    UNKNOWN_FOOT = 'sf#unknown'

    # MTB
    ASPHALT_MTB = 'sm#asphalt'
    CONCRETE_MTB = 'sm#concrete'
    COBBLESTONE_MTB = 'sm#cobblestone'
    PAVING_STONES_MTB = 'sm#paving_stones'
    PAVED_MTB = 'sm#paved'
    COMPACTED_MTB = 'sm#compacted'
    GRAVEL_MTB = 'sm#gravel'
    GRASS_PAVER_MTB = 'sm#grass_paver'
    WOOD_MTB = 'sm#wood'
    UNPAVED_MTB = 'sm#unpaved'
    SAND_MTB = 'sm#sand'
    GROUND_MTB = 'sm#ground'
    STONE_MTB = 'sm#stone'
    NATURE_MTB = 'sm#nature'
    ALPIN_MTB = 'sm#alpin'
    UNKNOWN_MTB = 'sm#unknown'
