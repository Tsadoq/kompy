"""Komoot tours (planned routes and recorded activities)."""

from __future__ import annotations

import copy
import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Self

import gpxpy
import requests
from gpxpy.gpx import GPX, GPXException

from kompy._http import DEFAULT_TIMEOUT, USER_AGENT, raise_for_status
from kompy._parsing import (
    coerce_optional_enum,
    link_href,
    optional_bool,
    optional_float,
    optional_int,
    optional_str,
    parse_datetime,
    parse_list,
    parse_list_or_none,
    parse_optional,
    require_int,
    require_str,
)
from kompy.constants.activities import SupportedActivities
from kompy.constants.privacy_status import PrivacyStatus
from kompy.constants.tour_constants import SmartTourTypes, TourTypes
from kompy.constants.urls import KomootUrl
from kompy.coordinate import Coordinate
from kompy.difficulty import Difficulty
from kompy.exceptions import KomootConnectionError, KomootResponseError, KomootTimeoutError
from kompy.image import KomootImage
from kompy.segment import AnnotatedSegment, Segment, SegmentInformation
from kompy.surface import Surface
from kompy.user import User
from kompy.way_type import WayType
from kompy.waypoint import Waypoint

if TYPE_CHECKING:
    from kompy.authentication import Authentication

__all__ = ['Tour', 'TourInformation', 'TourSummary']


@dataclass
class TourInformation:
    """
    A piece of information about stretches of a planned tour, e.g. that they are off grid or dangerous.

    :param tour_information_type: Kind of information, e.g. ``'OFF_GRID'`` or ``'MODERATE_DANGER'``.
    :param segments: The stretches of the tour the information applies to.
    """

    tour_information_type: str
    segments: list[SegmentInformation]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build the information from the API shape ``{"type": "OFF_GRID", "segments": [{"from", "to"}, ...]}``.

        :param data: One entry of a tour's ``tour_information``.
        :return: The parsed information; malformed segments are skipped.
        :raises KeyError: If ``type`` is missing.
        """
        return cls(
            tour_information_type=require_str(data, 'type'),
            segments=parse_list(data.get('segments'), SegmentInformation.from_dict),
        )


@dataclass
class TourSummary:
    """
    Breakdown of a planned tour by surface and by way type.

    :param surfaces: Share of the tour on each surface.
    :param way_types: Share of the tour on each way type.
    """

    surfaces: list[Surface]
    way_types: list[WayType]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build the summary from the API shape ``{"surfaces": [...], "way_types": [...]}``.

        :param data: The ``summary`` payload of a tour.
        :return: The parsed summary; malformed entries are skipped.
        """
        return cls(
            surfaces=parse_list(data.get('surfaces'), Surface.from_dict),
            way_types=parse_list(data.get('way_types'), WayType.from_dict),
        )


class Tour:
    """
    A Komoot tour: either a planned route or a recorded activity.

    Field reference: https://static.komoot.de/doc/external-api/v007/docson/index.html#../schemas/users_tours.schema.json

    Parsing is lenient so that changes to the (unofficial) API do not make tours unreadable: optional fields that
    are missing or malformed are ``None``, and enumeration values kompy does not know yet (a new sport, surface, ...)
    are kept as plain strings. Every attribute is always defined. The original payload is available as :attr:`raw`.

    Two tours are equal when they have the same :attr:`id`.

    :param tour: The tour payload returned by the API.
    :raises KeyError: If the payload has no ``id``.
    :raises ValueError: If the ``id`` is not an integer.
    """

    def __init__(self, tour: Mapping[str, Any]) -> None:  # noqa: PLR0915 - one statement per attribute, kept together on purpose
        embedded = tour.get('_embedded')
        if not isinstance(embedded, Mapping):
            embedded = {}
        links = tour.get('_links')

        self.raw: dict[str, Any] = dict(tour)
        """The payload the tour was parsed from."""

        # Identity and metadata
        self.id: int = require_int(tour, 'id')
        """Unique identifier of the tour (an integer, as returned by the API)."""
        self.type: TourTypes | str | None = coerce_optional_enum(TourTypes, tour.get('type'))
        """``'tour_planned'`` or ``'tour_recorded'``, see :class:`kompy.constants.TourTypes`."""
        self.name: str | None = optional_str(tour.get('name'))
        self.source: str | None = optional_str(tour.get('source'))
        """Where the tour comes from (a JSON string describing the app or integration that created it)."""
        self.status: PrivacyStatus | str | None = coerce_optional_enum(PrivacyStatus, tour.get('status'))
        """Visibility of the tour, see :class:`kompy.constants.PrivacyStatus`."""
        self.sport: SupportedActivities | str | None = coerce_optional_enum(SupportedActivities, tour.get('sport'))
        """Sport of the tour, see :class:`kompy.constants.SupportedActivities`."""
        self.start_date: datetime | None = parse_datetime(tour.get('date'))
        """When the tour started (recorded) or was planned for (planned)."""
        self.changed_at: datetime | None = parse_datetime(tour.get('changed_at'))
        self.device_name: str | None = optional_str(tour.get('device_name'))
        """Name of the device that recorded the tour, if known."""
        self.creator: User | None = parse_optional(embedded.get('creator'), User.from_dict)

        # Metrics
        self.distance: float | None = optional_float(tour.get('distance'))
        """Length of the tour, in meters."""
        self.total_duration: int | None = optional_int(tour.get('duration'))
        """Duration of the tour, in seconds (including pauses for recorded tours)."""
        self.time_in_motion: int | None = optional_int(tour.get('time_in_motion'))
        """Time spent moving, in seconds."""
        self.elevation_up: float | None = optional_float(tour.get('elevation_up'))
        """Elevation gain, in meters."""
        self.elevation_down: float | None = optional_float(tour.get('elevation_down'))
        """Elevation loss, in meters."""
        self.kcal_active: float | None = optional_float(tour.get('kcal_active'))
        self.kcal_resting: float | None = optional_float(tour.get('kcal_resting'))
        self.start_point: Coordinate | None = parse_optional(tour.get('start_point'), Coordinate.from_dict)

        # Planned tours only
        self.constitution: int | None = optional_int(tour.get('constitution'))
        """Fitness level (1 to 5) the tour was planned for."""
        self.query: str | None = optional_str(tour.get('query'))
        """Opaque routing query the tour was planned with."""
        self.smart_tour_type: SmartTourTypes | str | None = coerce_optional_enum(
            SmartTourTypes, tour.get('smart_tour_type')
        )
        self.poor_quality: bool | None = optional_bool(tour.get('poor_quality'))
        self.path: list[Waypoint] | None = parse_list_or_none(tour.get('path'), Waypoint.from_dict)
        self.segments: list[Segment] | None = parse_list_or_none(tour.get('segments'), Segment.from_dict)
        self.tour_information: list[TourInformation] | None = parse_list_or_none(
            tour.get('tour_information'), TourInformation.from_dict
        )
        self.summary: TourSummary | None = parse_optional(tour.get('summary'), TourSummary.from_dict)
        self.difficulty: Difficulty | None = parse_optional(tour.get('difficulty'), Difficulty.from_dict)

        # Images
        self.map_image: KomootImage | None = parse_optional(tour.get('map_image'), KomootImage.from_dict)
        """Large map of the tour (templated)."""
        self.map_image_preview: KomootImage | None = parse_optional(
            tour.get('map_image_preview'), KomootImage.from_dict
        )
        self.vector_map_image: KomootImage | None = parse_optional(tour.get('vector_map_image'), KomootImage.from_dict)
        self.vector_map_image_preview: KomootImage | None = parse_optional(
            tour.get('vector_map_image_preview'), KomootImage.from_dict
        )

        # Links
        self.master_share_url: str | None = optional_str(tour.get('master_share_url'))
        self.links_dict: dict[str, Any] | None = dict(links) if isinstance(links, Mapping) else None
        """The HAL ``_links`` of the tour."""
        self.coordinates_link: str | None = link_href(links, 'coordinates')

        # Embedded resources (see ``KomootConnector.get_tour_by_id(..., embedded=...)``)
        self.way_type_segments: list[AnnotatedSegment] = self._embedded_items(embedded, 'way_types')
        """Way type of each stretch of the tour; empty unless ``way_types`` was embedded."""
        self.surface_segments: list[AnnotatedSegment] = self._embedded_items(embedded, 'surfaces')
        """Surface of each stretch of the tour; empty unless ``surfaces`` was embedded."""

        # Filled from the payload when embedded, or later by the connector
        self.coordinates: list[Coordinate] = []
        """Coordinates of the tour; empty unless embedded or fetched with ``get_tour_coordinates``."""
        coordinates = embedded.get('coordinates')
        if isinstance(coordinates, Mapping):
            self.coordinates = parse_list(coordinates.get('items'), Coordinate.from_dict)
        self.gpx_track: GPX | None = None
        """GPX track of the tour; ``None`` unless fetched."""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build a tour from the API payload. Equivalent to ``Tour(data)``.

        :param data: The tour payload returned by the API.
        :return: The parsed tour.
        :raises KeyError: If the payload has no ``id``.
        :raises ValueError: If the ``id`` is not an integer.
        """
        return cls(data)

    def to_dict(self) -> dict[str, Any]:
        """
        Get the payload the tour was parsed from.

        :return: A deep copy of :attr:`raw`, safe to modify.
        """
        return copy.deepcopy(self.raw)

    @staticmethod
    def _embedded_items(embedded: Mapping[str, Any], key: str) -> list[AnnotatedSegment]:
        """Parse the ``items`` of an embedded ``way_types``/``surfaces`` resource."""
        resource = embedded.get(key)
        if not isinstance(resource, Mapping):
            return []
        return parse_list(resource.get('items'), AnnotatedSegment.from_dict)

    # ----------------------------------------------------------------- convenience

    @property
    def is_recorded(self) -> bool:
        """Whether the tour is a recorded activity."""
        return self.type == TourTypes.TOUR_RECORDED

    @property
    def is_planned(self) -> bool:
        """Whether the tour is a planned route."""
        return self.type == TourTypes.TOUR_PLANNED

    @property
    def url(self) -> str:
        """Link to the tour on komoot.com."""
        return f'https://www.komoot.com/tour/{self.id}'

    @property
    def distance_km(self) -> float | None:
        """Length of the tour, in kilometers."""
        return None if self.distance is None else self.distance / 1000

    @property
    def duration_timedelta(self) -> timedelta | None:
        """Duration of the tour (:attr:`total_duration`) as a timedelta."""
        return None if self.total_duration is None else timedelta(seconds=self.total_duration)

    @property
    def time_in_motion_timedelta(self) -> timedelta | None:
        """Time spent moving (:attr:`time_in_motion`) as a timedelta."""
        return None if self.time_in_motion is None else timedelta(seconds=self.time_in_motion)

    @property
    def tour_summary(self) -> TourSummary | None:
        """Alias of :attr:`summary`."""
        return self.summary

    def set_coordinates(self, coordinates: Iterable[Coordinate]) -> None:
        """
        Attach coordinates fetched separately (used by ``KomootConnector.get_tour_coordinates``).

        :param coordinates: The coordinates of the tour, in order.
        """
        self.coordinates = list(coordinates)

    def set_gpx_track(self, gpx_track: GPX) -> None:
        """
        Attach a GPX track fetched separately (used by ``KomootConnector.get_tour_gpx``).

        :param gpx_track: The GPX track of the tour.
        """
        self.gpx_track = gpx_track

    # ----------------------------------------------------------------- dunder methods

    def __repr__(self) -> str:
        date = self.start_date.date().isoformat() if self.start_date is not None else None
        sport = None if self.sport is None else str(self.sport)
        return f'Tour(id={self.id!r}, name={self.name!r}, sport={sport!r}, date={date!r})'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Tour):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    # ----------------------------------------------------------------- deprecated network helpers

    def generate_coordinates(self, authentication: Authentication) -> bool:
        """
        Fetch the coordinates of the tour and store them in :attr:`coordinates`.

        .. deprecated:: 0.1.0
           Use ``KomootConnector.get_tour_coordinates(tour)`` instead.

        :param authentication: The authentication of a logged-in connector (``connector.authentication``).
        :return: ``True`` once the coordinates are stored.
        :raises kompy.exceptions.KomootError: If the request fails or the response cannot be parsed.
        """
        warnings.warn(
            'Tour.generate_coordinates() is deprecated; use KomootConnector.get_tour_coordinates() instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        url = self.coordinates_link or f'{KomootUrl.TOUR_URL.format(tour_identifier=self.id)}/coordinates'
        response = _deprecated_get(url, authentication, accept='application/hal+json, application/json')
        try:
            items = response.json()['items']
        except (ValueError, KeyError, TypeError) as error:
            raise KomootResponseError(f'Unexpected coordinates payload for tour {self.id}.') from error
        self.set_coordinates(parse_list(items, Coordinate.from_dict))
        return True

    def generate_gpx_track(self, authentication: Authentication) -> bool:
        """
        Fetch the GPX track of the tour and store it in :attr:`gpx_track`.

        .. deprecated:: 0.1.0
           Use ``KomootConnector.get_tour_gpx(tour_id)`` instead.

        :param authentication: The authentication of a logged-in connector (``connector.authentication``).
        :return: ``True`` once the track is stored.
        :raises kompy.exceptions.KomootError: If the request fails or the response is not valid GPX.
        """
        warnings.warn(
            'Tour.generate_gpx_track() is deprecated; use KomootConnector.get_tour_gpx() instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        url = f'{KomootUrl.TOUR_URL.format(tour_identifier=self.id)}.gpx'
        response = _deprecated_get(url, authentication, accept='application/gpx+xml')
        try:
            gpx_track = gpxpy.parse(response.text)
        except GPXException as error:
            raise KomootResponseError(f'The GPX track of tour {self.id} could not be parsed.') from error
        self.set_gpx_track(gpx_track)
        return True


def _basic_auth(authentication: Authentication) -> tuple[str, str]:
    """
    Pick the credentials for a request: the API token after login, the email and password otherwise.

    :param authentication: The authentication object.
    :return: A ``(user, password)`` pair for HTTP basic auth.
    """
    try:
        return authentication.get_username(), authentication.get_token()
    except ValueError:
        return authentication.get_email_address(), authentication.get_password()


def _deprecated_get(url: str, authentication: Authentication, *, accept: str) -> requests.Response:
    """
    Perform a GET for the deprecated ``Tour.generate_*`` methods, mapping failures to kompy exceptions.

    :param url: The URL to fetch.
    :param authentication: The authentication object.
    :param accept: Value of the ``Accept`` header.
    :return: The successful (2xx) response.
    :raises KomootTimeoutError: If the request times out.
    :raises KomootConnectionError: If the API cannot be reached.
    :raises KomootAPIError: If the API answers with a non-2xx status (or one of its subclasses).
    """
    try:
        response = requests.get(
            url,
            auth=_basic_auth(authentication),
            headers={'Accept': accept, 'User-Agent': USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.Timeout as error:
        raise KomootTimeoutError(f'Request to {url} timed out.') from error
    except requests.RequestException as error:
        raise KomootConnectionError(f'Could not connect to {url}.') from error
    raise_for_status(response)
    return response
