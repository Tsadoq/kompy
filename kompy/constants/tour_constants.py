from typing import Final


class TourTypes:
    """
    Types of tour.
    """
    TOUR_PLANNED: Final[str] = 'tour_planned'
    TOUR_RECORDED: Final[str] = 'tour_recorded'


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
