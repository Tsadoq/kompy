from typing import (
    Final,
    List,
)


class PossibleWayType:
    """
    Possible way types.
    The complete list can be found at https://static.komoot.de/doc/external-api/v007/waytypes.html
    """
    FERRY: Final[str] = 'wt#ferry'
    ALPINE_BIKE_D9: Final[str] = 'wt#alpine_bike_d9'
    ALPINE_BIKE_D8: Final[str] = 'wt#alpine_bike_d8'
    TRAIL_D7: Final[str] = 'wt#trail_d7'
    TRAIL_D6: Final[str] = 'wt#trail_d6'
    TRAIL_D5: Final[str] = 'wt#trail_d5'
    TRAIL_D4: Final[str] = 'wt#trail_d4'
    TRAIL_D3: Final[str] = 'wt#trail_d3'
    TRAIL_D2: Final[str] = 'wt#trail_d2'
    TRAIL_D1: Final[str] = 'wt#trail_d1'
    HIKE_D9: Final[str] = 'wt#hike_d9'
    HIKE_D8: Final[str] = 'wt#hike_d8'
    HIKE_D7: Final[str] = 'wt#hike_d7'
    HIKE_D6: Final[str] = 'wt#hike_d6'
    HIKE_D5: Final[str] = 'wt#hike_d5'
    HIKE_D4: Final[str] = 'wt#hike_d4'
    HIKE_D3: Final[str] = 'wt#hike_d3'
    HIKE_D2: Final[str] = 'wt#hike_d2'
    HIKING_PATH: Final[str] = 'wt#hiking_path'
    LONG_HIKING_PATH: Final[str] = 'wt#long_hiking_path'
    ALPINE_HIKING_PATH: Final[str] = 'wt#alpine_hiking_path'
    TRACK: Final[str] = 'wt#track'
    WAY: Final[str] = 'wt#way'
    MINOR_ROAD: Final[str] = 'wt#minor_road'
    STREET: Final[str] = 'wt#street'
    PRIMARY: Final[str] = 'wt#primary'
    SERVICE: Final[str] = 'wt#service'
    CYCLEWAY: Final[str] = 'wt#cycleway'
    CYCLE_ROUTE: Final[str] = 'wt#cycle_route'
    FOOTWAY: Final[str] = 'wt#footway'
    MOVABLE_BRIDGE: Final[str] = 'wt#movable_bridge'
    UNKNOWN: Final[str] = 'wt#unknown'
    OFF_GRID: Final[str] = 'wt#off_grid'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all supported waytypes.
        :return: A list of all supported waytypes
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]
