from typing import (
    Dict,
    Final,
    List,
    Optional,
    Union,
)


class TourQueryParameters:
    """
    Query parameters for the tour list.
    """
    LIMIT: Final[str] = 'limit'
    PAGE: Final[str] = 'page'
    STATUS: Final[str] = 'status'
    TYPE: Final[str] = 'type'
    ONLY_UNLOCKED: Final[str] = 'only_unlocked'
    CENTER: Final[str] = 'center'
    MAX_DISTANCE: Final[str] = 'max_distance'
    SPORT_TYPES: Final[str] = 'sport_types'
    START_DATE: Final[str] = 'start_date'
    END_DATE: Final[str] = 'end_date'
    NAME: Final[str] = 'name'
    SORT_DIRECTION: Final[str] = 'sort_direction'
    SORT_FIELD: Final[str] = 'sort_field'

    @classmethod
    def construct_tour_query(
        cls,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        status: Optional[str] = None,
        tour_type: Optional[str] = None,
        only_unlocked: Optional[bool] = None,
        center: Optional[str] = None,
        max_distance: Optional[int] = None,
        sport_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        name: Optional[str] = None,
        sort_direction: Optional[str] = None,
        sort_field: Optional[str] = None,
    ) -> Dict[str, Union[str, int, bool, List[str]]]:
        """
        Construct a tour query.
        :param limit: the limit parameter of the query
        :param page: the page parameter of the query
        :param status: the status parameter of the query
        :param tour_type: the tour type parameter of the query
        :param only_unlocked: the only unlocked parameter of the query
        :param center: the center parameter of the query
        :param max_distance: the max distance parameter of the query
        :param sport_types: the sport types parameter of the query
        :param start_date: the start date parameter of the query
        :param end_date: the end date parameter of the query
        :param name: the name parameter of the query
        :param sort_direction: the sort direction parameter of the query
        :param sort_field: the sort field parameter of the query
        :return: a dictionary containing the query parameters
        """
        params = {
            cls.LIMIT: limit,
            cls.PAGE: page,
            cls.STATUS: status,
            cls.TYPE: tour_type,
            cls.ONLY_UNLOCKED: only_unlocked if only_unlocked is not None else None,
            cls.CENTER: center,
            cls.MAX_DISTANCE: max_distance,
            cls.SPORT_TYPES: sport_types,
            cls.START_DATE: start_date,
            cls.END_DATE: end_date,
            cls.NAME: name,
            cls.SORT_DIRECTION: sort_direction,
            cls.SORT_FIELD: sort_field,
        }

        return {
            key: value for key, value in params.items() if value is not None
        }
