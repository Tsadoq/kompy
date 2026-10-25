"""
Client for the Komoot API.

:class:`KomootConnector` logs in to Komoot and exposes the API as Python methods: list, fetch, download, upload,
edit and delete tours, and read users and highlights.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from email.utils import parseaddr
from itertools import islice
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Self, overload

import dateutil.parser
import gpxpy
import requests
from gpxpy.gpx import GPX, GPXException

from kompy._http import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TIMEOUT,
    HttpClient,
    Timeout,
    build_url,
    decode_json_object,
)
from kompy._parsing import parse_optional
from kompy.authentication import Authentication
from kompy.constants.activities import SupportedActivities
from kompy.constants.privacy_status import PrivacyStatus
from kompy.constants.query_parameters import TourQueryParameters
from kompy.constants.tour_constants import TourSort, TourSortField, TourTypes
from kompy.constants.tour_object_types import TourObjectTypes
from kompy.constants.urls import KomootUrl
from kompy.coordinate import Coordinate
from kompy.errors.initialisation_errors import NotEmailError
from kompy.errors.privacy_errors import PrivacyError
from kompy.exceptions import (
    AuthenticationError,
    DownloadError,
    KomootAPIError,
    KomootError,
    KomootResponseError,
    UnsupportedFormatError,
    UploadStatusError,
)
from kompy.highlight import Highlight
from kompy.image import KomootImage
from kompy.tour import Tour
from kompy.user import User

if TYPE_CHECKING:
    from types import TracebackType

    from fit_tool.fit_file import FitFile

__all__ = [
    'DEFAULT_EMBEDDED',
    'DEFAULT_PAGE_SIZE',
    'FILTERED_PAGE_SIZE',
    'KomootConnector',
    'TourFormat',
    'UploadResult',
]

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE: Final[int] = 100
"""Number of items requested per page when paginating (the API accepts larger pages, but 100 keeps them light)."""

FILTERED_PAGE_SIZE: Final[int] = 1000
"""Page size used when a ``status`` filter is applied locally: Komoot ignores that filter for one's own tours, so
every tour has to be listed, and large pages (the API accepts several thousand tours per page) keep that to a few
requests even when no tour matches."""

DEFAULT_EMBEDDED: Final[tuple[str, ...]] = ('coordinates', 'way_types', 'surfaces', 'directions')
"""Resources embedded in a tour by ``get_tour_by_id(..., embedded=True)``."""

TourFormat = Literal['gpx', 'fit']
"""File formats a tour can be exported to."""

_HAL_JSON: Final[str] = 'application/hal+json, application/json'
_FILE_MEDIA_TYPES: Final[dict[str, str]] = {'gpx': 'application/gpx+xml', 'fit': 'application/vnd.ant.fit'}
_UPLOAD_SUFFIXES: Final[dict[str, str]] = {'.gpx': 'gpx', '.fit': 'fit', '.tcx': 'tcx'}
_CENTER_PATTERN: Final[re.Pattern[str]] = re.compile(r'^\s*([-+]?\d{1,2}(?:\.\d+)?)\s*,\s*([-+]?\d{1,3}(?:\.\d+)?)\s*$')
_SLUG_MAX_LENGTH: Final[int] = 80
_REVOKED_CREDENTIALS_MESSAGE: Final[str] = (
    'Komoot rejected the token (revoked or invalid). Log in again with email/password to obtain a new one.'
)


@dataclass(frozen=True)
class UploadResult:
    """
    Outcome of :meth:`KomootConnector.upload_tour`.

    An ``UploadResult`` is always truthy, so code written for older kompy versions (where ``upload_tour`` returned
    ``True``) keeps working.

    :param tour_id: Id of the uploaded tour, or of the identical tour that already existed.
    :param created: ``True`` if a new tour was created (HTTP 201), ``False`` if Komoot recognised the file as a
        duplicate of an existing tour and kept that one (HTTP 202).
    :param raw: The tour payload returned by the API.
    """

    tour_id: int
    created: bool
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __bool__(self) -> bool:
        return True

    @property
    def status(self) -> str | None:
        """The visibility of the tour (``'private'``, ``'friends'`` or ``'public'``), if Komoot reported it."""
        status = self.raw.get('status')
        return status if isinstance(status, str) else None


class KomootConnector:
    """
    A logged-in connection to the Komoot API.

    Creating a connector logs in with the email address and password; every later request is authenticated with
    the username and API token returned by that login, so the password is not sent again. To avoid storing the
    password, create a connector from a saved token with :meth:`from_token`, or from environment variables with
    :meth:`from_env`.

    The connector holds an HTTP session: close it with :meth:`close`, or use the connector as a context manager::

        with KomootConnector(email='you@example.com', password='...') as connector:
            tours = connector.get_tours(limit=10)

    :param email: Email address of the Komoot account.
    :param password: Password of the Komoot account.
    :param timeout: Timeout in seconds of every request, either one value or a ``(connect, read)`` pair.
    :param max_retries: How many times read-only requests are retried on connection errors and on HTTP
        429/502/503/504 (honouring ``Retry-After``). ``0`` disables retries.
    :param session: A ``requests.Session`` to use (e.g. configured with proxies). It is not closed by :meth:`close`.
    :raises NotEmailError: If ``email`` is not an email address.
    :raises AuthenticationError: If Komoot rejects the email address or password.
    :raises KomootError: If the login fails for another reason (network, server error, unexpected response).
    """

    authentication: Authentication
    """The credentials of the connector."""

    def __init__(
        self,
        email: str,
        password: str,
        *,
        timeout: Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        if '@' not in parseaddr(email)[1]:
            raise NotEmailError(email)
        self._configure(
            Authentication(email_address=email, password=password),
            timeout=timeout,
            max_retries=max_retries,
            session=session,
        )
        try:
            self._login()
        except BaseException:
            self.close()
            raise

    # ----------------------------------------------------------------- construction

    @classmethod
    def from_token(
        cls,
        username: str,
        token: str,
        *,
        validate: bool = False,
        timeout: Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> Self:
        """
        Create a connector from the username and token of a previous login, without sending the password.

        The token (see :attr:`token`) is a long-lived, password-equivalent key: store it like a password. It is
        checked lazily, by the first request, unless ``validate`` is true.

        :param username: The username returned by the login (:attr:`username`).
        :param token: The API token returned by the login (:attr:`token`).
        :param validate: Check the token right away with one cheap request.
        :param timeout: See :class:`KomootConnector`.
        :param max_retries: See :class:`KomootConnector`.
        :param session: See :class:`KomootConnector`.
        :return: The connector.
        :raises ValueError: If ``username`` or ``token`` is empty.
        :raises AuthenticationError: If ``validate`` is true and Komoot rejects the token.
        """
        connector = cls.__new__(cls)
        connector._configure(
            Authentication(username=username, token=token),
            timeout=timeout,
            max_retries=max_retries,
            session=session,
        )
        connector._http.auth = (username, token)
        if validate:
            try:
                connector._get_json(build_url(KomootUrl.USER_PROFILE_URL, user_identifier=username))
            except BaseException:
                connector.close()
                raise
        return connector

    @classmethod
    def from_env(
        cls,
        prefix: str = 'KOMOOT_',
        *,
        timeout: Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> Self:
        """
        Create a connector from environment variables.

        ``<prefix>USERNAME`` and ``<prefix>TOKEN`` are used when both are set (see :meth:`from_token`); otherwise
        ``<prefix>EMAIL`` and ``<prefix>PASSWORD`` are used to log in.

        :param prefix: Prefix of the variable names.
        :param timeout: See :class:`KomootConnector`.
        :param max_retries: See :class:`KomootConnector`.
        :param session: See :class:`KomootConnector`.
        :return: The connector.
        :raises ValueError: If neither pair of variables is set.
        :raises KomootError: If the login fails (see :class:`KomootConnector`).
        """
        options: dict[str, Any] = {'timeout': timeout, 'max_retries': max_retries, 'session': session}
        username, token = os.environ.get(f'{prefix}USERNAME'), os.environ.get(f'{prefix}TOKEN')
        if username and token:
            return cls.from_token(username, token, **options)
        email, password = os.environ.get(f'{prefix}EMAIL'), os.environ.get(f'{prefix}PASSWORD')
        if email and password:
            return cls(email, password, **options)
        raise ValueError(
            f'No Komoot credentials found in the environment: set {prefix}USERNAME and {prefix}TOKEN, '
            f'or {prefix}EMAIL and {prefix}PASSWORD.'
        )

    def _configure(
        self,
        authentication: Authentication,
        *,
        timeout: Timeout,
        max_retries: int,
        session: requests.Session | None,
    ) -> None:
        """Set the attributes shared by every way of creating a connector."""
        self.authentication = authentication
        self._http = HttpClient(timeout=timeout, max_retries=max_retries, session=session)

    def _login(self) -> None:
        """
        Log in with the email address and password, and switch to token authentication.

        :raises AuthenticationError: If the credentials are rejected.
        :raises KomootResponseError: If the login response lacks the username or token.
        """
        email = self.authentication.get_email_address()
        url = build_url(KomootUrl.USER_LOGIN_URL, email_address=email)
        try:
            payload = self._http.request_json('GET', url, auth=(email, self.authentication.get_password()))
        except AuthenticationError as error:
            raise AuthenticationError(
                'Komoot rejected the email address or password.',
                status_code=error.status_code,
                url=error.url,
                body=error.body,
            ) from error
        username, token = payload.get('username'), payload.get('password')
        if not username or not token:
            raise KomootResponseError('Unexpected login response from Komoot: the username or token is missing.')
        self.authentication.set_username(str(username))
        self.authentication.set_token(str(token))
        self._http.auth = (str(username), str(token))
        logger.info('Logged in to Komoot as %s.', username)

    # ----------------------------------------------------------------- session management

    @property
    def username(self) -> str:
        """The username of the logged-in account (often numeric)."""
        return self.authentication.get_username()

    @property
    def token(self) -> str:
        """The API token of the account. It is password-equivalent: store it like a password."""
        return self.authentication.get_token()

    def close(self) -> None:
        """Close the HTTP session (a session passed to the constructor is left open)."""
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return f'{type(self).__name__}(username={self.username!r})'

    # ----------------------------------------------------------------- tours: listing

    def get_tours(
        self,
        limit: int | None = None,
        user_identifier: str | None = None,
        page: int | None = None,
        status: str | None = None,
        tour_type: str | None = None,
        only_unlocked: bool | None = False,
        center: str | None = None,
        max_distance: float | None = None,
        sport_types: Sequence[str] | None = None,
        start_date: str | date | datetime | None = None,
        end_date: str | date | datetime | None = None,
        tour_name: str | None = None,
        sort: str | None = None,
        sort_field: str | None = None,
        *,
        page_size: int | None = None,
    ) -> list[Tour]:
        """
        Get a list of tours.

        All pages are fetched until ``limit`` tours are collected (or the tours run out). Use :meth:`iter_tours` to
        process tours lazily, one page at a time.

        :param limit: The maximum number of tours to return; all tours when ``None``.
        :param user_identifier: The user whose tours to list; the logged-in user when ``None``.
        :param page: Fetch only this page (starting at 0) instead of all pages. Its size is ``page_size``, or
            ``limit`` when ``page_size`` is not given (100 when neither is), so ``page=2, limit=10`` returns the
            tours 20 to 29. A ``status`` filter does not change which tours a page holds; it is applied to them
            afterwards, so the page may contain fewer tours.
        :param status: Only return tours with this :class:`kompy.constants.PrivacyStatus`. ``None`` returns every
            tour the caller can see (all of their own tours; the public tours of other users). Komoot ignores this
            filter for one's own tours, so kompy also applies it locally.
        :param tour_type: Only return tours of this :class:`kompy.constants.TourTypes`.
        :param only_unlocked: Only return unlocked tours.
        :param center: Only return tours near this point, given as ``'lat,lng'`` (e.g. ``'52.52,13.40'``).
            Requires ``max_distance``.
        :param max_distance: Maximum distance from ``center``, in meters.
        :param sport_types: Only return tours of these sports (see :class:`kompy.constants.SupportedActivities`).
        :param start_date: Only return tours from this date on, given as a date, a datetime, or a string such as
            ``'2023-01-31'``. Naive values are taken to be in UTC.
        :param end_date: Only return tours up to this date (same formats as ``start_date``).
        :param tour_name: Only return tours whose name contains this text (case-insensitive).
        :param sort: Sort direction, a :class:`kompy.constants.TourSort`.
        :param sort_field: Field to sort by, a :class:`kompy.constants.TourSortField`. ``'proximity'`` requires
            ``center``.
        :param page_size: Number of tours requested per page. Defaults to ``limit`` when ``page`` is given; otherwise
            to ``min(limit, 100)`` (100 without ``limit``), or :data:`FILTERED_PAGE_SIZE` with a ``status`` filter.
        :return: The tours.
        :raises ValueError: If an argument is invalid.
        :raises TypeError: If ``sport_types`` is not a list of strings.
        :raises PrivacyError: If non-public tours of another user are requested.
        :raises KomootResponseError: If Komoot returned tours but none of them could be parsed.
        :raises KomootError: If a request fails.
        """
        return list(
            self.iter_tours(
                limit=limit,
                user_identifier=user_identifier,
                page=page,
                status=status,
                tour_type=tour_type,
                only_unlocked=only_unlocked,
                center=center,
                max_distance=max_distance,
                sport_types=sport_types,
                start_date=start_date,
                end_date=end_date,
                tour_name=tour_name,
                sort=sort,
                sort_field=sort_field,
                page_size=page_size,
            )
        )

    def iter_tours(
        self,
        limit: int | None = None,
        user_identifier: str | None = None,
        page: int | None = None,
        status: str | None = None,
        tour_type: str | None = None,
        only_unlocked: bool | None = False,
        center: str | None = None,
        max_distance: float | None = None,
        sport_types: Sequence[str] | None = None,
        start_date: str | date | datetime | None = None,
        end_date: str | date | datetime | None = None,
        tour_name: str | None = None,
        sort: str | None = None,
        sort_field: str | None = None,
        *,
        page_size: int | None = None,
    ) -> Iterator[Tour]:
        """
        Iterate over tours, fetching pages lazily as the iteration goes on.

        Takes the same arguments as :meth:`get_tours`. The arguments are validated right away; requests are only
        sent while iterating.

        :return: An iterator over the tours.
        :raises ValueError: If an argument is invalid.
        :raises TypeError: If ``sport_types`` is not a list of strings.
        :raises PrivacyError: If non-public tours of another user are requested.
        """
        _check_non_negative(limit=limit, page=page)
        if page_size is not None and page_size < 1:
            raise ValueError(f'page_size must be 1 or greater, got {page_size}.')
        user_identifier = user_identifier if user_identifier is not None else self.username
        own_tours = user_identifier == self.username

        status_filter = None if status is None else _validate_status(status)
        if status_filter is not None and status_filter != PrivacyStatus.PUBLIC and not own_tours:
            raise PrivacyError(user_identifier)
        # Komoot requires status=public to list the tours of another user.
        sent_status = status_filter if (status_filter is not None or own_tours) else PrivacyStatus.PUBLIC

        if page_size is None:
            page_size = _default_page_size(limit, page=page, filtered=status_filter is not None)

        query = TourQueryParameters.construct_tour_query(
            limit=page_size,
            status=sent_status,
            tour_type=_validate_tour_type(tour_type),
            only_unlocked=only_unlocked,
            sport_types=_validate_sport_types(sport_types),
            name=tour_name,
            **_location_query(center, max_distance, sort_field),
            **_date_query(start_date, end_date),
            sort_direction=_validate_choice('sort', sort, TourSort),
            sort_field=_validate_choice('sort_field', sort_field, TourSortField),
        )
        url = build_url(KomootUrl.LIST_TOURS_URL, user_identifier=user_identifier)
        tours = self._generate_tours(url, query, page=page, status_filter=status_filter)
        return tours if limit is None else islice(tours, limit)

    def _generate_tours(
        self,
        url: str,
        query: Mapping[str, Any],
        *,
        page: int | None,
        status_filter: PrivacyStatus | None,
    ) -> Iterator[Tour]:
        """Yield the parsed tours of the listing, skipping the ones that cannot be parsed."""
        seen = parsed = 0
        for items in self._iter_pages(url, query, key='tours', page=page):
            for item in items:
                seen += 1
                tour = _parse_tour(item)
                if tour is None:
                    continue
                parsed += 1
                if status_filter is None or tour.status == status_filter:
                    yield tour
            if seen and not parsed:
                raise KomootResponseError(
                    f'Failed to parse all {seen} returned tours. This may indicate an API/schema change.'
                )

    # ----------------------------------------------------------------- tours: single tour

    @overload
    def get_tour_by_id(
        self,
        tour_identifier: int | str | Tour,
        share_token: str | None = None,
        object_type: Literal[TourObjectTypes.KOMPY, 'kompy'] | None = None,
        *,
        embedded: bool | Sequence[str] = False,
    ) -> Tour: ...

    @overload
    def get_tour_by_id(
        self,
        tour_identifier: int | str | Tour,
        share_token: str | None = None,
        *,
        object_type: Literal[TourObjectTypes.GPX, 'gpx'],
        embedded: Literal[False] = False,
    ) -> GPX: ...

    @overload
    def get_tour_by_id(
        self,
        tour_identifier: int | str | Tour,
        share_token: str | None,
        object_type: Literal[TourObjectTypes.GPX, 'gpx'],
        *,
        embedded: Literal[False] = False,
    ) -> GPX: ...

    @overload
    def get_tour_by_id(
        self,
        tour_identifier: int | str | Tour,
        share_token: str | None = None,
        *,
        object_type: Literal[TourObjectTypes.FIT, 'fit'],
        embedded: Literal[False] = False,
    ) -> FitFile: ...

    @overload
    def get_tour_by_id(
        self,
        tour_identifier: int | str | Tour,
        share_token: str | None,
        object_type: Literal[TourObjectTypes.FIT, 'fit'],
        *,
        embedded: Literal[False] = False,
    ) -> FitFile: ...

    @overload
    def get_tour_by_id(
        self,
        tour_identifier: int | str | Tour,
        share_token: str | None = None,
        object_type: str | None = None,
        *,
        embedded: bool | Sequence[str] = False,
    ) -> Tour | GPX | FitFile: ...

    def get_tour_by_id(
        self,
        tour_identifier: int | str | Tour,
        share_token: str | None = None,
        object_type: str | None = None,
        *,
        embedded: bool | Sequence[str] = False,
    ) -> Tour | GPX | FitFile:
        """
        Get a tour by its id, as a :class:`kompy.Tour`, a GPX track or a FIT file.

        :param tour_identifier: The tour, or its id.
        :param share_token: A share token, which grants access to a tour regardless of its visibility.
        :param object_type: A :class:`kompy.constants.TourObjectTypes`, either ``'kompy'`` (default) for a
            :class:`kompy.Tour`, ``'gpx'`` for a ``gpxpy`` GPX object, ``'fit'`` for a ``fit_tool`` FitFile
            (planned tours only).
        :param embedded: Extra resources to embed in the tour (``'kompy'`` only). ``True`` embeds
            :data:`DEFAULT_EMBEDDED` (coordinates, way types, surfaces and directions); a list of names embeds
            those (the API also knows ``'participants'`` and ``'timeline'``).
        :return: The tour in the requested format.
        :raises ValueError: If ``object_type`` is unknown, or ``embedded`` is used with another format.
        :raises NotFoundError: If the tour does not exist.
        :raises UnsupportedFormatError: If a FIT file is requested for a recorded tour.
        :raises KomootError: If the request fails or the response cannot be parsed.
        """
        if not object_type or object_type == TourObjectTypes.KOMPY:
            return self._get_tour(tour_identifier, share_token=share_token, embedded=embedded)
        if object_type not in (TourObjectTypes.GPX, TourObjectTypes.FIT):
            raise ValueError(
                f'Invalid object type provided: {object_type}. Use one of {", ".join(TourObjectTypes.list_all())}.'
            )
        if embedded:
            raise ValueError('embedded is only supported when fetching a Tour object (object_type="kompy").')
        if object_type == TourObjectTypes.GPX:
            return self.get_tour_gpx(tour_identifier, share_token=share_token)
        return self.get_tour_fit(tour_identifier, share_token=share_token)

    def _get_tour(
        self, tour_identifier: int | str | Tour, *, share_token: str | None, embedded: bool | Sequence[str]
    ) -> Tour:
        """Fetch and parse a tour."""
        tour_id = _tour_id(tour_identifier)
        if embedded is True:
            resources: Sequence[str] = DEFAULT_EMBEDDED
        elif embedded is False:
            resources = ()
        elif isinstance(embedded, str):
            resources = (embedded,)
        else:
            resources = embedded
        params: dict[str, str] = {}
        if share_token:
            params['share_token'] = share_token
        if resources:
            params['_embedded'] = ','.join(resources)
            if 'directions' in resources:
                params['directions'] = 'v2'
        payload = self._get_json(build_url(KomootUrl.TOUR_URL, tour_identifier=tour_id), params=params)
        try:
            return Tour(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise KomootResponseError(f'The tour {tour_id} could not be parsed: {error!r}') from error

    def get_tour_gpx(self, tour_identifier: int | str | Tour, share_token: str | None = None) -> GPX:
        """
        Get the GPX track of a tour (planned or recorded).

        If a :class:`kompy.Tour` is given, the track is also stored on it (``tour.gpx_track``).

        :param tour_identifier: The tour, or its id.
        :param share_token: A share token, which grants access to a tour regardless of its visibility.
        :return: The parsed ``gpxpy`` GPX object.
        :raises NotFoundError: If the tour does not exist.
        :raises KomootResponseError: If the response is not valid GPX.
        :raises KomootError: If the request fails.
        """
        content = self._get_tour_file(tour_identifier, 'gpx', share_token=share_token)
        try:
            gpx = gpxpy.parse(content.decode('utf-8'))
        except (GPXException, UnicodeDecodeError) as error:
            raise KomootResponseError(f'The GPX track of tour {_tour_id(tour_identifier)} is invalid.') from error
        if isinstance(tour_identifier, Tour):
            tour_identifier.set_gpx_track(gpx)
        return gpx

    def get_tour_fit(self, tour_identifier: int | str | Tour, share_token: str | None = None) -> FitFile:
        """
        Get the FIT file of a planned tour (Komoot does not export recorded tours as FIT).

        :param tour_identifier: The tour, or its id.
        :param share_token: A share token, which grants access to a tour regardless of its visibility.
        :return: The parsed ``fit_tool`` FitFile.
        :raises UnsupportedFormatError: If the tour is a recorded tour.
        :raises NotFoundError: If the tour does not exist.
        :raises KomootResponseError: If the response is not a valid FIT file.
        :raises KomootError: If the request fails.
        """
        content = self._get_tour_file(tour_identifier, 'fit', share_token=share_token)
        from fit_tool.fit_file import FitFile  # noqa: PLC0415 - fit_tool configures logging when imported

        try:
            return FitFile.from_bytes(content)
        except Exception as error:  # fit_tool raises assorted exception types for malformed files
            raise KomootResponseError(f'The FIT file of tour {_tour_id(tour_identifier)} is invalid.') from error

    def get_tour_coordinates(self, tour_identifier: int | str | Tour) -> list[Coordinate]:
        """
        Get all coordinates of a tour.

        If a :class:`kompy.Tour` is given, the coordinates are also stored on it (``tour.coordinates``).

        :param tour_identifier: The tour, or its id.
        :return: The coordinates, in order; ``time`` is the offset from the start in milliseconds.
        :raises NotFoundError: If the tour does not exist.
        :raises KomootResponseError: If the response has no list of coordinates.
        :raises KomootError: If the request fails.
        """
        tour_id = _tour_id(tour_identifier)
        payload = self._get_json(build_url(KomootUrl.TOUR_COORDINATES_URL, tour_identifier=tour_id))
        items = payload.get('items')
        if not isinstance(items, list):
            raise KomootResponseError(f'Unexpected coordinates payload for tour {tour_id}: no "items" list.')
        coordinates = [coordinate for item in items if (coordinate := parse_optional(item, Coordinate.from_dict))]
        if isinstance(tour_identifier, Tour):
            tour_identifier.set_coordinates(coordinates)
        return coordinates

    def get_tour_cover_images(self, tour_identifier: int | str | Tour) -> list[KomootImage]:
        """
        Get the cover images (photos) of a tour.

        :param tour_identifier: The tour, or its id.
        :return: The images; often empty. Their URLs may be templated, see :meth:`KomootImage.url_for`.
        :raises NotFoundError: If the tour does not exist.
        :raises KomootError: If a request fails.
        """
        url = build_url(KomootUrl.TOUR_COVER_IMAGES_URL, tour_identifier=_tour_id(tour_identifier))
        images: list[KomootImage] = []
        for items in self._iter_pages(url, {'limit': DEFAULT_PAGE_SIZE}, key='items'):
            images.extend(image for item in items if (image := parse_optional(item, KomootImage.from_dict)))
        return images

    # ----------------------------------------------------------------- tours: downloads

    def download_tour(
        self,
        tour_identifier: int | str | Tour,
        path: str | os.PathLike[str],
        fmt: TourFormat = 'gpx',
        *,
        share_token: str | None = None,
    ) -> Path:
        """
        Download a tour as a GPX or FIT file, saving the bytes exactly as Komoot sends them.

        :param tour_identifier: The tour, or its id.
        :param path: The file to write, or a directory: an existing one, or a new one written with a trailing
            separator (``'backup/'``). In a directory the file is named ``<id>_<name>.<fmt>`` when a
            :class:`kompy.Tour` is given, and ``<id>.<fmt>`` otherwise. Missing directories are created, and an
            existing file is overwritten.
        :param fmt: ``'gpx'`` or ``'fit'`` (FIT is only available for planned tours).
        :param share_token: A share token, which grants access to a tour regardless of its visibility.
        :return: The path of the written file.
        :raises ValueError: If ``fmt`` is not supported.
        :raises UnsupportedFormatError: If a FIT file is requested for a recorded tour.
        :raises KomootError: If the request fails.
        :raises OSError: If the file cannot be written.
        """
        fmt = _validate_format(fmt)
        target = Path(path)
        if target.is_dir() or _names_directory(path):
            target /= tour_filename(tour_identifier, fmt)
        content = self._get_tour_file(tour_identifier, fmt, share_token=share_token)
        _write_atomically(target, content)
        logger.debug('Downloaded tour %s to %s.', _tour_id(tour_identifier), target)
        return target

    def download_tours(
        self,
        dest_dir: str | os.PathLike[str],
        fmt: TourFormat = 'gpx',
        *,
        overwrite: bool = False,
        **filters: Any,
    ) -> list[Path]:
        """
        Download many tours as files named ``<id>_<name>.<fmt>`` into a directory, e.g. to back up an account.

        A tour that fails to download does not stop the others: once all tours are processed, a
        :class:`kompy.exceptions.DownloadError` lists the failures and the files that were written. FIT files only
        exist for planned tours, so combine ``fmt='fit'`` with ``tour_type=TourTypes.TOUR_PLANNED``.

        :param dest_dir: The directory to write to; it is created if missing.
        :param fmt: ``'gpx'`` or ``'fit'``.
        :param overwrite: Download tours whose file already exists again (by default they are skipped, so an
            interrupted backup can be resumed). A file counts as existing under either name kompy gives it,
            ``<id>_<name>.<fmt>`` or ``<id>.<fmt>``, so a renamed tour is not downloaded twice.
        :param filters: Filters selecting the tours, as accepted by :meth:`get_tours` (e.g. ``limit``,
            ``tour_type``, ``sport_types``, ``start_date``).
        :return: The files of all selected tours, including the existing ones that were skipped.
        :raises ValueError: If ``fmt`` or a filter is invalid.
        :raises DownloadError: If some tours could not be downloaded.
        :raises KomootError: If listing the tours fails.
        :raises OSError: If a file cannot be written.
        """
        fmt = _validate_format(fmt)
        directory = Path(dest_dir)
        directory.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        failures: dict[int, KomootError] = {}
        for tour in self.iter_tours(**filters):
            target = directory / tour_filename(tour, fmt)
            existing = None if overwrite else find_downloaded_tour(directory, tour.id, fmt)
            if existing is not None:
                logger.debug('Skipping tour %s: %s already exists.', tour.id, existing)
                target = existing
            else:
                try:
                    self.download_tour(tour, target, fmt)
                except KomootError as error:
                    logger.warning('Could not download tour %s: %s', tour.id, error)
                    failures[tour.id] = error
                    continue
            paths.append(target)
        if failures:
            raise DownloadError(
                f'{len(failures)} tour(s) could not be downloaded: {", ".join(map(str, failures))}.',
                paths=paths,
                failures=failures,
            )
        return paths

    def _get_tour_file(self, tour_identifier: int | str | Tour, fmt: TourFormat, *, share_token: str | None) -> bytes:
        """Fetch the raw bytes of a tour exported as GPX or FIT."""
        tour_id = _tour_id(tour_identifier)
        url = f'{build_url(KomootUrl.TOUR_URL, tour_identifier=tour_id)}.{fmt}'
        params = {'share_token': share_token} if share_token else None
        try:
            response = self._request('GET', url, params=params, headers={'Accept': _FILE_MEDIA_TYPES[fmt]})
        except KomootAPIError as error:
            if fmt == 'fit' and error.status_code == 400:
                raise UnsupportedFormatError(
                    f'Tour {tour_id} cannot be exported as FIT: Komoot only provides FIT files for planned tours. '
                    'Use GPX for recorded tours.'
                ) from error
            raise
        if not response.content:
            raise KomootResponseError(f'The {fmt.upper()} file of tour {tour_id} is empty.')
        return response.content

    # ----------------------------------------------------------------- tours: changes

    def upload_tour(
        self,
        tour_object: GPX | FitFile | str | os.PathLike[str],
        activity_type: str,
        tour_name: str,
        time_in_motion: int | None = None,
        status: str | None = PrivacyStatus.FRIENDS,
    ) -> UploadResult:
        """
        Upload a tour from a GPX object, a FIT object, or a ``.gpx``, ``.fit`` or ``.tcx`` file.

        Komoot's upload endpoint ignores the requested visibility and gives every new tour the default visibility
        of the account. kompy therefore checks the visibility of the created tour and, when it differs from
        ``status``, changes it right away with :meth:`change_tour` (so for a moment, between the two requests, the
        tour has the default visibility). If Komoot recognises the file as a duplicate
        (``created`` is ``False``), the existing tour is left untouched: neither its name nor its visibility is
        changed.

        :param tour_object: A ``gpxpy`` GPX object, a ``fit_tool`` FitFile, or the path of a file.
        :param activity_type: The sport, one of :class:`kompy.constants.SupportedActivities` (unknown values are
            sent anyway, with a warning, in case Komoot added a sport kompy does not know yet). Komoot applies it
            only to GPX uploads: FIT and TCX files carry their own sport. Use :meth:`change_tour` to change the
            sport afterwards.
        :param tour_name: The name of the tour.
        :param time_in_motion: The time in motion in seconds (GPX and TCX only), i.e. the duration minus the pauses.
            It must not be larger than the duration of the tour. Ignored for FIT files, which carry it themselves.
        :param status: The :class:`kompy.constants.PrivacyStatus` of the new tour, friends by default. ``None``
            keeps the default visibility of the account.
        :return: The id of the tour, whether it was created or already existed, and its visibility
            (``result.status``). The result is always truthy, but no longer equal to ``True``.
        :raises TypeError: If ``tour_object`` is not a GPX object, a FitFile or a path.
        :raises ValueError: If the file type, ``status`` or ``time_in_motion`` is invalid.
        :raises OSError: If the file cannot be read.
        :raises KomootAPIError: If Komoot rejects the upload.
        :raises UploadStatusError: If the tour was uploaded but its visibility could not be set; the error holds
            the id of the tour, so it can be fixed or deleted.
        :raises KomootError: If the request fails or the response cannot be parsed.
        """
        status = None if status is None else _validate_status(status)
        _check_sport(activity_type)
        data_type, body = _upload_body(tour_object)
        params: dict[str, Any] = {'data_type': data_type, 'sport': activity_type, 'name': tour_name, 'status': status}
        if time_in_motion is not None:
            if time_in_motion < 0:
                raise ValueError(f'time_in_motion must be 0 or greater, got {time_in_motion}.')
            if data_type == 'fit':
                logger.warning('time_in_motion is ignored for FIT files, which carry it themselves.')
            else:
                params['time_in_motion'] = time_in_motion
        response = self._request(
            'POST',
            KomootUrl.UPLOAD_TOUR_URL,
            params=params,
            data=body,
            headers={'Content-Type': 'application/octet-stream', 'Accept': _HAL_JSON},
        )
        payload = decode_json_object(response)
        try:
            tour_id = int(payload['id'])
        except (KeyError, TypeError, ValueError) as error:
            raise KomootResponseError('The upload response from Komoot has no valid tour id.') from error
        created = response.status_code != 202
        if not created:
            logger.info('Komoot already had this tour (id %s); no new tour was created.', tour_id)
            return UploadResult(tour_id=tour_id, created=False, raw=payload)
        logger.info('Uploaded tour %s.', tour_id)
        if status is not None and payload.get('status') != status:
            payload = self._apply_upload_status(tour_id, status, payload)
        return UploadResult(tour_id=tour_id, created=True, raw=payload)

    def _apply_upload_status(self, tour_id: int, status: PrivacyStatus, payload: dict[str, Any]) -> dict[str, Any]:
        """Give a just uploaded tour the requested visibility, which the upload endpoint ignores."""
        actual = payload.get('status')
        actual_status = actual if isinstance(actual, str) else None
        logger.debug('Tour %s was uploaded as %s; changing it to %s.', tour_id, actual_status, status)
        try:
            self.change_tour(tour_id, status=status)
        except KomootError as error:
            raise UploadStatusError(
                f'Tour {tour_id} was uploaded with visibility {actual_status or "unknown"}, but changing it to '
                f'{status} failed ({error}). Change it with change_tour() or delete the tour.',
                tour_id=tour_id,
                requested_status=str(status),
                actual_status=actual_status,
            ) from error
        return {**payload, 'status': str(status)}

    def change_tour(
        self,
        tour_id: int | str | Tour,
        activity_type: str | None = None,
        tour_name: str | None = None,
        status: str | None = None,
    ) -> bool:
        """
        Change the sport, name and/or privacy status of an existing tour. Only the given fields are changed.

        :param tour_id: The tour, or its id.
        :param activity_type: The new sport, one of :class:`kompy.constants.SupportedActivities`.
        :param tour_name: The new name.
        :param status: The new :class:`kompy.constants.PrivacyStatus`.
        :return: ``True`` (failures raise).
        :raises ValueError: If nothing is to be changed, or ``status`` is invalid.
        :raises NotFoundError: If the tour does not exist.
        :raises KomootError: If the request fails.
        """
        payload: dict[str, str] = {}
        if activity_type is not None:
            _check_sport(activity_type)
            payload['sport'] = str(activity_type)
        if tour_name is not None:
            payload['name'] = tour_name
        if status is not None:
            payload['status'] = str(_validate_status(status))
        if not payload:
            raise ValueError('Nothing to change: give at least one of activity_type, tour_name or status.')
        tour_id = _tour_id(tour_id)
        self._request(
            'PATCH',
            build_url(KomootUrl.TOUR_URL, tour_identifier=tour_id),
            json=payload,
            headers={'Accept': _HAL_JSON},
        )
        logger.info('Changed tour %s (%s).', tour_id, ', '.join(payload))
        return True

    def delete_tour(self, tour_id: int | str | Tour) -> bool:
        """
        Delete a tour.

        The request is not retried: if a gateway error hides a delete that succeeded, a retry would wrongly report
        the tour as missing.

        :param tour_id: The tour, or its id.
        :return: ``True`` (failures raise).
        :raises NotFoundError: If the tour does not exist.
        :raises KomootError: If the request fails.
        """
        tour_id = _tour_id(tour_id)
        self._request('DELETE', build_url(KomootUrl.TOUR_URL, tour_identifier=tour_id), headers={'Accept': _HAL_JSON})
        logger.info('Deleted tour %s.', tour_id)
        return True

    # ----------------------------------------------------------------- users and highlights

    def get_user(self, username: str | None = None) -> User:
        """
        Get a user profile.

        For the logged-in user this is the full profile (with locale, units and creation date); for other users it
        is the public profile (with the premium flag).

        :param username: The user; the logged-in user when ``None``.
        :return: The user.
        :raises NotFoundError: If the user does not exist.
        :raises KomootError: If the request fails or the response cannot be parsed.
        """
        username = username if username is not None else self.username
        template = KomootUrl.USER_URL if username == self.username else KomootUrl.USER_PROFILE_URL
        payload = self._get_json(build_url(template, user_identifier=username))
        try:
            return User.from_dict(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise KomootResponseError(f'The profile of user {username} could not be parsed: {error!r}') from error

    def get_user_highlights(
        self,
        username: str | None = None,
        limit: int | None = None,
        *,
        page_size: int | None = None,
    ) -> list[Highlight]:
        """
        Get the highlights a user recommended.

        :param username: The user; the logged-in user when ``None``.
        :param limit: The maximum number of highlights to return; all when ``None``.
        :param page_size: Number of highlights requested per page; defaults to ``min(limit, 100)``, or 100.
        :return: The highlights.
        :raises ValueError: If ``limit`` or ``page_size`` is invalid.
        :raises KomootError: If a request fails.
        """
        return list(self.iter_user_highlights(username, limit, page_size=page_size))

    def iter_user_highlights(
        self,
        username: str | None = None,
        limit: int | None = None,
        *,
        page_size: int | None = None,
    ) -> Iterator[Highlight]:
        """
        Iterate over the highlights a user recommended, fetching pages lazily.

        Takes the same arguments as :meth:`get_user_highlights`.

        :return: An iterator over the highlights.
        :raises ValueError: If ``limit`` or ``page_size`` is invalid.
        """
        _check_non_negative(limit=limit)
        if page_size is not None and page_size < 1:
            raise ValueError(f'page_size must be 1 or greater, got {page_size}.')
        if page_size is None:
            page_size = min(limit, DEFAULT_PAGE_SIZE) if limit else DEFAULT_PAGE_SIZE
        url = build_url(KomootUrl.USER_HIGHLIGHTS_URL, user_identifier=username or self.username)
        highlights = self._generate_highlights(url, {'limit': page_size})
        return highlights if limit is None else islice(highlights, limit)

    def _generate_highlights(self, url: str, query: Mapping[str, Any]) -> Iterator[Highlight]:
        """Yield the parsed highlights of a listing, skipping the ones that cannot be parsed."""
        for items in self._iter_pages(url, query, key='items'):
            for item in items:
                if not isinstance(item, Mapping):
                    logger.warning('Skipping a highlight that is not a JSON object: %r', item)
                    continue
                try:
                    yield Highlight.from_dict(item)
                except (KeyError, TypeError, ValueError) as error:
                    logger.warning('Skipping a highlight that could not be parsed: %r', error)

    def get_highlight(self, highlight_id: int | str) -> Highlight:
        """
        Get a highlight.

        :param highlight_id: The id of the highlight.
        :return: The highlight.
        :raises NotFoundError: If the highlight does not exist.
        :raises KomootError: If the request fails or the response cannot be parsed.
        """
        payload = self._get_json(build_url(KomootUrl.HIGHLIGHT_URL, highlight_identifier=highlight_id))
        try:
            return Highlight.from_dict(payload)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise KomootResponseError(f'The highlight {highlight_id} could not be parsed: {error!r}') from error

    # ----------------------------------------------------------------- HTTP helpers

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Send an authenticated request; a 401 means the token is no longer accepted."""
        try:
            return self._http.request(method, url, **kwargs)
        except AuthenticationError as error:
            if error.status_code != 401:
                raise
            raise AuthenticationError(
                _REVOKED_CREDENTIALS_MESSAGE, status_code=error.status_code, url=error.url, body=error.body
            ) from error

    def _get_json(self, url: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """GET a JSON object."""
        return decode_json_object(self._request('GET', url, params=params, headers={'Accept': _HAL_JSON}))

    def _iter_pages(
        self,
        url: str,
        query: Mapping[str, Any],
        *,
        key: str,
        page: int | None = None,
    ) -> Iterator[list[Any]]:
        """
        Yield the items (``_embedded[key]``) of each page of a paginated HAL listing.

        :param url: The listing URL.
        :param query: The query parameters, without ``page``.
        :param key: The key of the items in ``_embedded``.
        :param page: Fetch only this page; all pages from the first one when ``None``.
        """
        number = 0 if page is None else page
        while True:
            payload = self._get_json(url, params={**query, TourQueryParameters.PAGE: number})
            items = _embedded_items(payload, key)
            yield items
            if page is not None or not items or not _has_next_page(payload, number):
                return
            number += 1


# ----------------------------------------------------------------- module helpers


def tour_filename(tour_identifier: int | str | Tour, fmt: str) -> str:
    """
    Build the file name of a downloaded tour: ``<id>_<slugified name>.<fmt>``, or ``<id>.<fmt>`` without a name.

    >>> tour_filename(Tour({'id': 42, 'name': 'Über den Säntis!'}), 'gpx')
    '42_uber-den-santis.gpx'

    :param tour_identifier: The tour, or its id.
    :param fmt: The file extension.
    :return: The file name.
    """
    tour_id = _tour_id(tour_identifier)
    name = tour_identifier.name if isinstance(tour_identifier, Tour) else None
    slug = _slugify(name) if name else ''
    return f'{tour_id}_{slug}.{fmt}' if slug else f'{tour_id}.{fmt}'


def find_downloaded_tour(directory: Path, tour_id: int | str, fmt: str) -> Path | None:
    """
    Find the file of a tour downloaded earlier into a directory, under either name kompy uses for it.

    :param directory: The download directory.
    :param tour_id: The id of the tour.
    :param fmt: The file extension.
    :return: The existing file (``<id>.<fmt>`` first, then ``<id>_<name>.<fmt>``), or ``None``.
    """
    plain = directory / f'{tour_id}.{fmt}'
    if plain.is_file():
        return plain
    named = sorted(path for path in directory.glob(f'{tour_id}_*.{fmt}') if path.is_file())
    return named[0] if named else None


def _slugify(text: str) -> str:
    """Turn a name into a short, lowercase, ASCII-only string safe in file names on every OS."""
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_text.lower()).strip('-')
    return slug[:_SLUG_MAX_LENGTH].rstrip('-')


def _names_directory(path: str | os.PathLike[str]) -> bool:
    """Tell whether a path ends with a separator, i.e. names a directory even if it does not exist yet."""
    text = os.fspath(path)
    separators = tuple(separator for separator in (os.sep, os.altsep) if separator)
    return text.endswith(separators)


def _write_atomically(target: Path, content: bytes) -> None:
    """
    Write a file through a uniquely named temporary sibling, so an interrupted download never leaves a truncated
    file, a failed one leaves nothing behind, and concurrent downloads of the same file do not interleave.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f'.{target.name}.{secrets.token_hex(8)}.part'
    # Unlike tempfile.mkstemp (always 0600), mode 0o666 lets the umask decide, like a plain open() would.
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_BINARY', 0), 0o666)
    try:
        with os.fdopen(descriptor, 'wb') as file:
            file.write(content)
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _tour_id(tour_identifier: int | str | Tour) -> int | str:
    """Get the id of a tour given as a :class:`kompy.Tour` or as an id."""
    return tour_identifier.id if isinstance(tour_identifier, Tour) else tour_identifier


def _parse_tour(item: Any) -> Tour | None:
    """Parse a tour of a listing, or log a warning and return ``None`` if it cannot be parsed."""
    try:
        return Tour(item)
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        tour_id = item.get('id', 'unknown') if isinstance(item, Mapping) else 'unknown'
        logger.warning('Skipping tour %s: it could not be parsed (%r).', tour_id, error)
        return None


def _embedded_items(payload: Mapping[str, Any], key: str) -> list[Any]:
    """Get ``payload['_embedded'][key]``; HAL leaves ``_embedded`` out entirely when a listing is empty."""
    embedded = payload.get('_embedded')
    items = embedded.get(key) if isinstance(embedded, Mapping) else None
    return items if isinstance(items, list) else []


def _has_next_page(payload: Mapping[str, Any], number: int) -> bool:
    """Tell whether a page of a HAL listing is followed by another one."""
    page = payload.get('page')
    if isinstance(page, Mapping):
        total_pages, current = page.get('totalPages'), page.get('number')
        if isinstance(total_pages, int):
            return (current if isinstance(current, int) else number) + 1 < total_pages
    links = payload.get('_links')
    return isinstance(links, Mapping) and 'next' in links


def _default_page_size(limit: int | None, *, page: int | None, filtered: bool) -> int:
    """Choose the page size of a tour listing when the caller did not give one."""
    if page is not None:
        # An explicit page is a window of `limit` tours, whatever filter is applied to it afterwards.
        return limit or DEFAULT_PAGE_SIZE
    if filtered:
        # The status filter is applied locally and may discard most tours: few large pages beat many small ones.
        return FILTERED_PAGE_SIZE
    return min(limit, DEFAULT_PAGE_SIZE) if limit else DEFAULT_PAGE_SIZE


def _check_non_negative(**values: int | None) -> None:
    """Reject negative counts and page numbers."""
    for name, value in values.items():
        if value is not None and value < 0:
            raise ValueError(f'{name} must be 0 or greater, got {value}.')


def _validate_status(status: str) -> PrivacyStatus:
    """Turn a privacy status string into a :class:`PrivacyStatus`, rejecting unknown values."""
    try:
        return PrivacyStatus(status)
    except ValueError:
        raise ValueError(
            f'Invalid status provided: {status!r}. Use one of {", ".join(PrivacyStatus.list_all())}.'
        ) from None


def _validate_tour_type(tour_type: str | None) -> str | None:
    """Reject unknown tour types."""
    if tour_type is not None and tour_type not in TourTypes.list_all():
        raise ValueError(f'Invalid tour type provided: {tour_type}. Please provide a valid tour type.')
    return tour_type


def _validate_choice(name: str, value: str | None, choices: type[TourSort | TourSortField]) -> str | None:
    """Reject a value that is not one of the members of an enumeration."""
    if value is not None and value not in choices.list_all():
        raise ValueError(f'Invalid {name} provided: {value}. Use one of {", ".join(choices.list_all())}.')
    return value


def _check_sport(sport: str) -> None:
    """Warn about sports kompy does not know; Komoot adds sports over time, so they are not rejected."""
    if sport not in SupportedActivities.list_all():
        logger.warning('Unknown sport %r: sending it anyway, in case Komoot supports it.', sport)


def _validate_sport_types(sport_types: Sequence[str] | None) -> list[str] | None:
    """Check that the sport filter is a list of strings, warning about unknown sports."""
    if sport_types is None:
        return None
    if not isinstance(sport_types, list | tuple):
        raise TypeError(f'Invalid sport types provided: {sport_types}. Please provide a list of strings.')
    for sport_type in sport_types:
        if not isinstance(sport_type, str):
            raise TypeError(f'Invalid sport type provided: {sport_type}. Please provide a string.')
        _check_sport(sport_type)
    return list(sport_types)


def _location_query(center: str | None, max_distance: float | None, sort_field: str | None) -> dict[str, Any]:
    """Validate the location filter and return its query parameters."""
    if sort_field == TourSortField.PROXIMITY and center is None:
        raise ValueError('Sort field proximity requires a center to be provided.')
    if center is None:
        if max_distance is not None:
            logger.warning('max_distance is ignored because no center was given.')
        return {}
    match = _CENTER_PATTERN.match(center)
    if match is None:
        raise ValueError(
            f'Invalid center provided: {center}. '
            f'Please provide a valid center in the format "lat,lng" (e.g. "52.520008,13.404954").'
        )
    if max_distance is None:
        raise ValueError('Max distance must be provided if center is provided.')
    if max_distance <= 0:
        raise ValueError(f'max_distance must be greater than 0, got {max_distance}.')
    return {'center': f'{match[1]},{match[2]}', 'max_distance': max_distance}


def _date_query(start: str | date | datetime | None, end: str | date | datetime | None) -> dict[str, Any]:
    """Validate the date filter and return its query parameters (as datetimes)."""
    start_date = None if start is None else _to_datetime('start_date', start)
    end_date = None if end is None else _to_datetime('end_date', end)
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ValueError(f'Start date ({start_date}) must be before end date ({end_date}).')
    return {'start_date': start_date, 'end_date': end_date}


def _to_datetime(name: str, value: str | date | datetime) -> datetime:
    """Convert a date argument to an aware datetime (naive values are taken to be in UTC)."""
    if isinstance(value, str):
        try:
            value = dateutil.parser.parse(value)
        except (ValueError, OverflowError) as error:
            raise ValueError(f'Invalid {name} provided: {value!r} is not a date.') from error
    elif not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def _validate_format(fmt: str) -> TourFormat:
    """Check that a download format is supported."""
    if fmt == 'gpx':
        return 'gpx'
    if fmt == 'fit':
        return 'fit'
    raise ValueError(f'Unsupported format {fmt!r}: use "gpx" or "fit".')


def _upload_body(tour_object: object) -> tuple[str, bytes]:
    """Get the ``data_type`` and the bytes of a tour to upload."""
    if isinstance(tour_object, GPX):
        return 'gpx', tour_object.to_xml().encode('utf-8')
    if isinstance(tour_object, str | os.PathLike):
        path = Path(tour_object)
        data_type = _UPLOAD_SUFFIXES.get(path.suffix.lower())
        if data_type is None:
            raise ValueError(f'Cannot upload {path.name}: the file must end in .gpx, .fit or .tcx.')
        return data_type, path.read_bytes()
    from fit_tool.fit_file import FitFile  # noqa: PLC0415 - fit_tool configures logging when imported

    if isinstance(tour_object, FitFile):
        return 'fit', bytes(tour_object.to_bytes())
    raise TypeError(
        f'Invalid tour object provided: {type(tour_object)}. Please provide a GPX object, a FitFile or a file path.'
    )
