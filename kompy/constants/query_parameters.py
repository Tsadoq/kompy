"""Query parameters of the tour list endpoint and their serialization."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Final

__all__ = ['TourQueryParameters', 'format_api_datetime']


def format_api_datetime(value: date | datetime) -> str:
    """
    Format a date or datetime the way the Komoot API writes timestamps (ISO 8601, UTC, milliseconds).

    Naive datetimes are taken to be in UTC; dates stand for midnight UTC.

    >>> format_api_datetime(datetime(2023, 1, 2, 3, 4, 5))
    '2023-01-02T03:04:05.000Z'

    :param value: The date or datetime to format.
    :return: A timestamp such as ``'2023-01-02T03:04:05.000Z'``.
    """
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.isoformat(timespec='milliseconds').replace('+00:00', 'Z')


class TourQueryParameters:
    """Names of the query parameters accepted by the tour list endpoint."""

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
        limit: int | None = None,
        page: int | None = None,
        status: str | None = None,
        tour_type: str | None = None,
        only_unlocked: bool | None = None,
        center: str | None = None,
        max_distance: float | None = None,
        sport_types: Sequence[str] | None = None,
        start_date: date | datetime | str | None = None,
        end_date: date | datetime | str | None = None,
        name: str | None = None,
        sort_direction: str | None = None,
        sort_field: str | None = None,
    ) -> dict[str, str | int | float]:
        """
        Build the query string parameters of a tour list request, serialized the way the API expects them.

        Parameters that are ``None`` are left out. Values are not validated here (``KomootConnector.get_tours``
        does that). Serialization rules:

        * ``only_unlocked`` is sent as ``'true'`` only when it is true (``false`` is the server default);
        * ``sport_types`` is sent as one comma-separated value (the API documents it as a single string);
        * dates and datetimes are sent as ISO 8601 UTC timestamps (see :func:`format_api_datetime`); strings are
          sent unchanged;
        * enumeration members are sent as their plain string value.

        :param limit: Number of tours per page.
        :param page: Index of the page to fetch, starting at 0.
        :param status: Privacy status (``'public'`` is required for other users' tours).
        :param tour_type: ``'tour_planned'`` or ``'tour_recorded'``.
        :param only_unlocked: Whether to only list unlocked tours.
        :param center: Center of the search area, as ``'lat,lng'``.
        :param max_distance: Maximum distance from ``center``, in meters.
        :param sport_types: Sports to include.
        :param start_date: Only list tours from this date on.
        :param end_date: Only list tours up to this date.
        :param name: Case-insensitive substring of the tour name.
        :param sort_direction: ``'asc'`` or ``'desc'``.
        :param sort_field: Field to sort by.
        :return: The query parameters, ready to be passed to ``requests``.
        """
        params: dict[str, str | int | float | None] = {
            cls.LIMIT: limit,
            cls.PAGE: page,
            cls.STATUS: _plain(status),
            cls.TYPE: _plain(tour_type),
            cls.ONLY_UNLOCKED: 'true' if only_unlocked else None,
            cls.CENTER: center,
            cls.MAX_DISTANCE: max_distance,
            cls.SPORT_TYPES: ','.join(str(sport) for sport in sport_types) if sport_types else None,
            cls.START_DATE: _date_param(start_date),
            cls.END_DATE: _date_param(end_date),
            cls.NAME: name,
            cls.SORT_DIRECTION: _plain(sort_direction),
            cls.SORT_FIELD: _plain(sort_field),
        }
        return {key: value for key, value in params.items() if value is not None}


def _plain(value: str | None) -> str | None:
    """Turn an enumeration member into its plain string value (``str()`` of a StrEnum member is its value)."""
    return None if value is None else str(value)


def _date_param(value: date | datetime | str | None) -> str | None:
    """Serialize a date query parameter; strings are assumed to be formatted already."""
    if value is None or isinstance(value, str):
        return value
    return format_api_datetime(value)
