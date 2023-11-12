from typing import (
    Final,
    List,
)


class TourTypes:
    """
    Types of tour.
    """
    TOUR_PLANNED: Final[str] = 'tour_planned'
    TOUR_RECORDED: Final[str] = 'tour_recorded'


class SmartTourTypes:
    """
    Types of smart tour. For smart tours api format=v2 only
    """
    SMART_TOUR_PLAIN: Final[str] = 'SMART_TOUR_PLAIN'
    SMART_TOUR_CUSTOMIZED: Final[str] = 'SMART_TOUR_CUSTOMIZED'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all supported activities.
        :return: A list of all supported activities
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]


class TourSort:
    """
    Sort direction of the tour list, can be either ascending or descending.
    """
    ASCENDING: Final[str] = 'asc'
    DESCENDING: Final[str] = 'desc'


class TourSortField:
    """
    Field to sort the tour list by, can be one of name, elevation, duration, date, proximity
    """
    NAME: Final[str] = 'name'
    ELEVATION: Final[str] = 'elevation'
    DURATION: Final[str] = 'duration'
    DATE: Final[str] = 'date'
    PROXIMITY: Final[str] = 'proximity'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all supported activities.
        :return: A list of all supported activities
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]
