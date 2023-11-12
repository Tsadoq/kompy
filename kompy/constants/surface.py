from typing import (
    Final,
    List,
)


class SurfaceType:
    """
    Surface types of the tour.
    The complete list can be found at https://static.komoot.de/doc/external-api/v007/surfaces.html
    """
    # Bike
    ASPHALT_BIKE: Final[str] = 'sb#asphalt'
    CONCRETE_BIKE: Final[str] = 'sb#concrete'
    PAVED_BIKE: Final[str] = 'sb#paved'
    PAVING_STONES_BIKE: Final[str] = 'sb#paving_stones'
    COBBLESTONE_BIKE: Final[str] = 'sb#cobblestone'
    COBBLES_BIKE: Final[str] = 'sb#cobbles'
    COMPACTED_BIKE: Final[str] = 'sb#compacted'
    GRAVEL_BIKE: Final[str] = 'sb#gravel'
    GRASS_PAVER_BIKE: Final[str] = 'sb#grass_paver'
    WOOD_BIKE: Final[str] = 'sb#wood'
    SAND_BIKE: Final[str] = 'sb#sand'
    GROUND_BIKE: Final[str] = 'sb#ground'
    STONE_BIKE: Final[str] = 'sb#stone'
    UNPAVED_BIKE: Final[str] = 'sb#unpaved'
    ALPIN_BIKE: Final[str] = 'sb#alpin'
    UNKNOWN_BIKE: Final[str] = 'sb#unknown'

    # Foot
    ASPHALT_FOOT: Final[str] = 'sf#asphalt'
    CONCRETE_FOOT: Final[str] = 'sf#concrete'
    COBBLESTONE_FOOT: Final[str] = 'sf#cobblestone'
    PAVING_STONES_FOOT: Final[str] = 'sf#paving_stones'
    PAVED_FOOT: Final[str] = 'sf#paved'
    COMPACTED_FOOT: Final[str] = 'sf#compacted'
    GRAVEL_FOOT: Final[str] = 'sf#gravel'
    GRASS_PAVER_FOOT: Final[str] = 'sf#grass_paver'
    WOOD_FOOT: Final[str] = 'sf#wood'
    UNPAVED_FOOT: Final[str] = 'sf#unpaved'
    SAND_FOOT: Final[str] = 'sf#sand'
    GROUND_FOOT: Final[str] = 'sf#ground'
    STONE_FOOT: Final[str] = 'sf#stone'
    NATURE_FOOT: Final[str] = 'sf#nature'
    ALPIN_FOOT: Final[str] = 'sf#alpin'
    UNKNOWN_FOOT: Final[str] = 'sf#unknown'

    # MTB
    ASPHALT_MTB: Final[str] = 'sm#asphalt'
    CONCRETE_MTB: Final[str] = 'sm#concrete'
    COBBLESTONE_MTB: Final[str] = 'sm#cobblestone'
    PAVING_STONES_MTB: Final[str] = 'sm#paving_stones'
    PAVED_MTB: Final[str] = 'sm#paved'
    COMPACTED_MTB: Final[str] = 'sm#compacted'
    GRAVEL_MTB: Final[str] = 'sm#gravel'
    GRASS_PAVER_MTB: Final[str] = 'sm#grass_paver'
    WOOD_MTB: Final[str] = 'sm#wood'
    UNPAVED_MTB: Final[str] = 'sm#unpaved'
    SAND_MTB: Final[str] = 'sm#sand'
    GROUND_MTB: Final[str] = 'sm#ground'
    STONE_MTB: Final[str] = 'sm#stone'
    NATURE_MTB: Final[str] = 'sm#nature'
    ALPIN_MTB: Final[str] = 'sm#alpin'
    UNKNOWN_MTB: Final[str] = 'sm#unknown'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all supported activities.
        :return: A list of all supported activities
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]
