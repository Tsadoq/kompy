from typing import (
    Final,
    List,
)


class SupportedActivities:
    """
    Activities that are supported by Komoot.

    Updated list can be found: https://static.komoot.de/doc/external-api/v007/sports.html
    """

    # Main sport types
    HIKING: Final[str] = 'hike'
    MOUNTAINEERING: Final[str] = 'mountaineering'
    ROAD_CYCLING: Final[str] = 'racebike'
    E_ROAD_CYCLING: Final[str] = 'e_racebike'
    BIKE_TOURING: Final[str] = 'touringbicycle'
    E_BIKE_TOURING: Final[str] = 'e_touringbicycle'
    MOUNTAIN_BIKING: Final[str] = 'mtb'
    E_MOUNTAIN_BIKING: Final[str] = 'e_mtb'
    GRAVEL_RIDING: Final[str] = 'mtb_easy'
    E_GRAVEL_RIDING: Final[str] = 'e_mtb_easy'
    ENDURO_MTB: Final[str] = 'mtb_advanced'
    E_ENDURO_MTB: Final[str] = 'e_mtb_advanced'
    RUNNING: Final[str] = 'jogging'

    # Tracking sport types
    CLIMBING: Final[str] = 'climbing'
    DOWNHILL: Final[str] = 'downhillbike'
    CROSS_COUNTRY_SKIING: Final[str] = 'nordic'
    NORDIC_WALKING: Final[str] = 'nordicwalking'
    SKATING: Final[str] = 'skaten'
    ALPINE_SKIING: Final[str] = 'skialpin'
    ALPINE_SKI_TOURING: Final[str] = 'skitour'
    SLEDDING: Final[str] = 'sled'
    SNOWBOARDING: Final[str] = 'snowboard'
    SNOW_SHOE: Final[str] = 'snowshoe'
    UNICYCLING: Final[str] = 'unicycle'
    BIKE: Final[str] = 'citybike'
    OTHER: Final[str] = 'other'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all supported activities.
        :return: A list of all supported activities
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]
