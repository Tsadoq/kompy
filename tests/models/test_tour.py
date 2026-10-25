"""Tests for :class:`kompy.Tour`, :class:`kompy.TourSummary` and :class:`kompy.TourInformation`."""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import requests
import responses
from gpxpy.gpx import GPX

from kompy import (
    Authentication,
    AuthenticationError,
    Coordinate,
    Difficulty,
    KomootAPIError,
    KomootConnectionError,
    KomootImage,
    KomootResponseError,
    KomootTimeoutError,
    NotFoundError,
    RateLimitError,
    Segment,
    SegmentInformation,
    ServerError,
    Surface,
    Tour,
    TourInformation,
    TourSummary,
    User,
    Waypoint,
    WayType,
)
from kompy._http import USER_AGENT
from kompy.constants import (
    DifficultyGrade,
    PossibleWayType,
    PrivacyStatus,
    SegmentType,
    SmartTourTypes,
    SupportedActivities,
    SurfaceType,
    TourTypes,
)
from tests.models._api import read_api_fixture

EXAMPLE_GPX = Path(__file__).parent.parent / 'resources' / 'example.gpx'

#: Every tour payload available in the fixtures, keyed by a readable test id.
ALL_TOUR_PAYLOADS = {
    **{
        f'list-item-{index}': tour
        for index, tour in enumerate(read_api_fixture('tours_list_page')['_embedded']['tours'])
    },
    'recorded-by-id': read_api_fixture('tour_recorded_by_id'),
    'planned-by-id': read_api_fixture('tour_planned_by_id'),
    'planned-by-id-embedded': read_api_fixture('tour_planned_by_id_embedded'),
}

#: Attributes that must exist on every tour, whatever the payload contains.
TOUR_ATTRIBUTES = [
    'id',
    'type',
    'name',
    'source',
    'status',
    'sport',
    'start_date',
    'changed_at',
    'device_name',
    'creator',
    'distance',
    'total_duration',
    'time_in_motion',
    'elevation_up',
    'elevation_down',
    'kcal_active',
    'kcal_resting',
    'start_point',
    'constitution',
    'query',
    'smart_tour_type',
    'poor_quality',
    'path',
    'segments',
    'tour_information',
    'summary',
    'difficulty',
    'map_image',
    'map_image_preview',
    'vector_map_image',
    'vector_map_image_preview',
    'master_share_url',
    'links_dict',
    'coordinates_link',
    'way_type_segments',
    'surface_segments',
    'coordinates',
    'gpx_track',
    'raw',
]

TOUR_URL = 'https://api.komoot.de/v007/tours/1000000001'
COORDINATES_URL = f'{TOUR_URL}/coordinates'
GPX_URL = f'{TOUR_URL}.gpx'


@pytest.fixture
def recorded_payload() -> dict[str, Any]:
    payload: dict[str, Any] = read_api_fixture('tour_recorded_by_id')
    return payload


@pytest.fixture
def planned_payload() -> dict[str, Any]:
    payload: dict[str, Any] = read_api_fixture('tour_planned_by_id')
    return payload


@pytest.fixture
def recorded_tour(recorded_payload: dict[str, Any]) -> Tour:
    return Tour(recorded_payload)


def _basic_auth_header(user: str, password: str) -> str:
    return 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()


# --------------------------------------------------------------------------- parsing real payloads


@pytest.mark.parametrize('payload', ALL_TOUR_PAYLOADS.values(), ids=ALL_TOUR_PAYLOADS.keys())
def test_every_fixture_tour_parses_with_all_attributes(payload: dict[str, Any]) -> None:
    tour = Tour(payload)

    for attribute in TOUR_ATTRIBUTES:
        getattr(tour, attribute)  # never raises AttributeError
    assert tour.id == payload['id']
    assert isinstance(tour.id, int)
    assert tour.sport == payload['sport']
    assert tour.status == payload['status']
    assert isinstance(tour.start_date, datetime)
    assert tour.start_date.tzinfo is not None
    assert tour.coordinates_link == payload['_links']['coordinates']['href']
    assert isinstance(tour.creator, User)
    assert tour.gpx_track is None


def test_recorded_tour_fields(recorded_tour: Tour) -> None:
    assert tour_fields(recorded_tour) == {
        'id': 1000000001,
        'type': TourTypes.TOUR_RECORDED,
        'name': 'Sample name',
        'status': PrivacyStatus.FRIENDS,
        'sport': SupportedActivities.RUNNING,
        'start_date': datetime(2026, 10, 24, 12, 46, 45, tzinfo=UTC),
        'changed_at': datetime(2026, 10, 24, 13, 49, 53, 474000, tzinfo=UTC),
        'device_name': 'Sample device_name',
        'distance': 12022.7099609375,
        'total_duration': 3753,
        'time_in_motion': 3753,
        'elevation_up': 56.0,
        'elevation_down': 53.0,
        'kcal_active': 0.0,
        'kcal_resting': 0.0,
        'start_point': Coordinate(46.006516, 8.007887, 579.4),
    }
    assert recorded_tour.source is not None
    assert 'garmin' in recorded_tour.source


def tour_fields(tour: Tour) -> dict[str, Any]:
    keys = [
        'id', 'type', 'name', 'status', 'sport', 'start_date', 'changed_at', 'device_name', 'distance',
        'total_duration', 'time_in_motion', 'elevation_up', 'elevation_down', 'kcal_active', 'kcal_resting',
        'start_point',
    ]  # fmt: skip
    return {key: getattr(tour, key) for key in keys}


def test_recorded_tour_has_no_planning_data(recorded_tour: Tour) -> None:
    assert recorded_tour.path is None
    assert recorded_tour.segments is None
    assert recorded_tour.tour_information is None
    assert recorded_tour.summary is None
    assert recorded_tour.difficulty is None
    assert recorded_tour.constitution is None
    assert recorded_tour.query is None
    assert recorded_tour.smart_tour_type is None
    assert recorded_tour.way_type_segments == []
    assert recorded_tour.surface_segments == []
    assert recorded_tour.coordinates == []


def test_recorded_tour_images(recorded_tour: Tour) -> None:
    assert isinstance(recorded_tour.map_image, KomootImage)
    assert recorded_tour.map_image.templated is True
    assert recorded_tour.map_image.url_for(width=200, height=100).endswith('?width=200&height=100')
    assert recorded_tour.map_image.attribution == 'Map data © OpenStreetMap contributors'
    assert isinstance(recorded_tour.map_image_preview, KomootImage)
    assert isinstance(recorded_tour.vector_map_image, KomootImage)
    assert recorded_tour.vector_map_image.templated is False
    assert recorded_tour.vector_map_image.media_type == 'image/*'
    assert isinstance(recorded_tour.vector_map_image_preview, KomootImage)


def test_creator_is_parsed(recorded_tour: Tour) -> None:
    assert recorded_tour.creator is not None
    assert recorded_tour.creator.username == '1234567890'
    assert recorded_tour.creator.is_premium is False


def test_convenience_properties(recorded_tour: Tour) -> None:
    assert recorded_tour.is_recorded is True
    assert recorded_tour.is_planned is False
    assert recorded_tour.url == 'https://www.komoot.com/tour/1000000001'
    assert recorded_tour.distance_km == pytest.approx(12.0227099609375)
    assert recorded_tour.duration_timedelta == timedelta(seconds=3753)
    assert recorded_tour.time_in_motion_timedelta == timedelta(seconds=3753)


def test_convenience_properties_without_data() -> None:
    tour = Tour({'id': 1})

    assert tour.is_recorded is False
    assert tour.is_planned is False
    assert tour.distance_km is None
    assert tour.duration_timedelta is None
    assert tour.time_in_motion_timedelta is None


def test_planned_tour_fields(planned_payload: dict[str, Any]) -> None:
    tour = Tour(planned_payload)

    assert tour.is_planned is True
    assert tour.constitution == 3
    assert tour.query == 'QUERYSTRING'
    assert tour.difficulty == Difficulty(DifficultyGrade.DIFFICULT, 'dj#t3', 'd#c3')
    assert tour.path is not None
    assert tour.path[0] == Waypoint(location=Coordinate(46.008358, 8.004328), index=0)
    assert [waypoint.index for waypoint in tour.path] == [0, 19, 33]
    assert tour.segments == [
        Segment(SegmentType.ROUTED, SegmentInformation(0, 19)),
        Segment(SegmentType.ROUTED, SegmentInformation(19, 33)),
        Segment(SegmentType.MANUAL, SegmentInformation(33, 90)),
    ]
    assert tour.tour_information is not None
    assert tour.tour_information[0] == TourInformation(
        tour_information_type='MODERATE_DANGER',
        segments=[SegmentInformation(691, 716), SegmentInformation(934, 935)],
    )
    assert [info.tour_information_type for info in tour.tour_information] == ['MODERATE_DANGER', 'OFF_GRID']


def test_planned_tour_summary(planned_payload: dict[str, Any]) -> None:
    tour = Tour(planned_payload)

    assert tour.summary is not None
    assert tour.summary.surfaces[0] == Surface(SurfaceType.ASPHALT_FOOT, 0.0044255382)
    assert [surface.type for surface in tour.summary.surfaces] == ['sf#asphalt', 'sf#unknown', 'sf#unpaved']
    assert tour.summary.way_types[1] == WayType(PossibleWayType.ALPINE_HIKING_PATH, 0.012233274)
    assert tour.tour_summary is tour.summary


def test_embedded_resources_are_parsed() -> None:
    tour = Tour(read_api_fixture('tour_planned_by_id_embedded'))

    assert tour.coordinates == [
        Coordinate(46.002166, 8.004221, 1728.6, 0),
        Coordinate(46.00029, 8.002217, 1728.2, 9661),
        Coordinate(46.004379, 8.004958, 1728, 12172),
    ]
    assert [(s.element, s.segment_boundaries) for s in tour.way_type_segments] == [
        ('wt#way', SegmentInformation(0, 33)),
        ('wt#off_grid', SegmentInformation(33, 90)),
        ('wt#way', SegmentInformation(90, 99)),
    ]
    assert [s.element for s in tour.surface_segments] == ['sf#gravel', 'sf#ground', 'sf#gravel']


# --------------------------------------------------------------------------- identity, repr, serialization


def test_repr(recorded_tour: Tour) -> None:
    assert repr(recorded_tour) == "Tour(id=1000000001, name='Sample name', sport='jogging', date='2026-10-24')"


def test_repr_without_optional_data() -> None:
    assert repr(Tour({'id': 5})) == 'Tour(id=5, name=None, sport=None, date=None)'


def test_equality_and_hash_use_the_id(recorded_payload: dict[str, Any]) -> None:
    renamed = {**recorded_payload, 'name': 'Renamed'}

    assert Tour(recorded_payload) == Tour(renamed)
    assert hash(Tour(recorded_payload)) == hash(Tour(renamed))
    assert len({Tour(recorded_payload), Tour(renamed)}) == 1
    assert Tour(recorded_payload) != Tour({**recorded_payload, 'id': 2})
    assert Tour(recorded_payload) != recorded_payload


def test_from_dict_is_equivalent_to_the_constructor(recorded_payload: dict[str, Any]) -> None:
    tour = Tour.from_dict(recorded_payload)

    assert isinstance(tour, Tour)
    assert tour == Tour(recorded_payload)
    assert tour.raw == recorded_payload


def test_to_dict_returns_a_deep_copy(recorded_tour: Tour, recorded_payload: dict[str, Any]) -> None:
    data = recorded_tour.to_dict()
    data['start_point']['lat'] = 0

    assert data != recorded_payload
    assert recorded_tour.to_dict() == recorded_payload


def test_set_coordinates_and_gpx_track(recorded_tour: Tour) -> None:
    gpx = GPX()

    recorded_tour.set_coordinates(iter([Coordinate(1, 2), Coordinate(3, 4)]))
    recorded_tour.set_gpx_track(gpx)

    assert recorded_tour.coordinates == [Coordinate(1, 2), Coordinate(3, 4)]
    assert recorded_tour.gpx_track is gpx


# --------------------------------------------------------------------------- lenient parsing


@pytest.mark.parametrize(
    ('mutate', 'attribute', 'expected'),
    [
        (lambda t: t.update(sport='e_road_bike_new'), 'sport', 'e_road_bike_new'),
        (lambda t: t.update(status='secret'), 'status', 'secret'),
        (lambda t: t.update(type='tour_imported'), 'type', 'tour_imported'),
        (lambda t: t.update(smart_tour_type='SMART_TOUR_X'), 'smart_tour_type', 'SMART_TOUR_X'),
        (lambda t: t.update(smart_tour_type=None), 'smart_tour_type', None),
        (lambda t: t['difficulty'].update(grade='expert'), 'difficulty', Difficulty('expert', 'dj#t3', 'd#c3')),
    ],
)
def test_unknown_enum_values_are_kept_as_strings(
    planned_payload: dict[str, Any],
    mutate: Callable[[dict[str, Any]], None],
    attribute: str,
    expected: Any,
) -> None:
    mutate(planned_payload)

    assert getattr(Tour(planned_payload), attribute) == expected


def test_known_smart_tour_type() -> None:
    tour = Tour({'id': 1, 'smart_tour_type': 'SMART_TOUR_PLAIN'})

    assert tour.smart_tour_type is SmartTourTypes.SMART_TOUR_PLAIN


def test_unknown_values_in_nested_lists_are_kept(planned_payload: dict[str, Any]) -> None:
    planned_payload['summary']['surfaces'].append({'type': 'sf#ice', 'amount': 0.1})
    planned_payload['summary']['way_types'].append({'type': 'wt#via_ferrata', 'amount': 0.2})
    planned_payload['segments'].append({'type': 'Imported', 'from': 90, 'to': 99})

    tour = Tour(planned_payload)

    assert tour.summary is not None
    assert tour.summary.surfaces[-1].type == 'sf#ice'
    assert tour.summary.way_types[-1].type == 'wt#via_ferrata'
    assert tour.segments is not None
    assert tour.segments[-1].segment_type == 'Imported'


def test_malformed_nested_entries_are_skipped(planned_payload: dict[str, Any]) -> None:
    planned_payload['summary']['surfaces'].append({'type': 'sf#asphalt', 'amount': 7})
    planned_payload['summary']['way_types'].append({'amount': 0.1})
    planned_payload['path'].append({'index': 40})
    planned_payload['segments'].append('junk')

    tour = Tour(planned_payload)

    assert tour.summary is not None
    assert len(tour.summary.surfaces) == 3
    assert len(tour.summary.way_types) == 3
    assert tour.path is not None
    assert len(tour.path) == 3
    assert tour.segments is not None
    assert len(tour.segments) == 3


def test_rounding_noise_in_summary_amounts_is_accepted(planned_payload: dict[str, Any]) -> None:
    planned_payload['summary']['surfaces'] = [{'type': 'sf#asphalt', 'amount': 1.0000001}]

    tour = Tour(planned_payload)

    assert tour.summary is not None
    assert tour.summary.surfaces == [Surface(SurfaceType.ASPHALT_FOOT, 1.0)]


def test_only_the_id_is_required() -> None:
    tour = Tour({'id': 42})

    assert tour.id == 42
    for attribute in TOUR_ATTRIBUTES:
        value = getattr(tour, attribute)
        if attribute == 'id':
            continue
        if attribute in ('way_type_segments', 'surface_segments', 'coordinates'):
            assert value == []
        elif attribute == 'raw':
            assert value == {'id': 42}
        else:
            assert value is None, attribute


@pytest.mark.parametrize(
    'missing_key',
    ['kcal_active', 'kcal_resting', 'vector_map_image', 'time_in_motion', 'source', 'device_name', 'status'],
)
def test_missing_optional_keys_become_none(recorded_payload: dict[str, Any], missing_key: str) -> None:
    del recorded_payload[missing_key]

    assert getattr(Tour(recorded_payload), missing_key) is None


def test_missing_altitude_in_start_point(recorded_payload: dict[str, Any]) -> None:
    del recorded_payload['start_point']['alt']

    assert Tour(recorded_payload).start_point == Coordinate(46.006516, 8.007887)


def test_missing_difficulty_explanations(planned_payload: dict[str, Any]) -> None:
    planned_payload['difficulty'] = {'grade': 'easy'}

    assert Tour(planned_payload).difficulty == Difficulty(DifficultyGrade.EASY)


def test_invalid_start_point_becomes_none(recorded_payload: dict[str, Any]) -> None:
    recorded_payload['start_point'] = {'lat': 999, 'lng': 8}

    assert Tour(recorded_payload).start_point is None


def test_invalid_dates_become_none(recorded_payload: dict[str, Any]) -> None:
    recorded_payload['date'] = 'yesterday'
    recorded_payload['changed_at'] = None

    tour = Tour(recorded_payload)

    assert tour.start_date is None
    assert tour.changed_at is None


def test_missing_links(recorded_payload: dict[str, Any]) -> None:
    del recorded_payload['_links']

    tour = Tour(recorded_payload)

    assert tour.links_dict is None
    assert tour.coordinates_link is None


def test_links_without_coordinates(recorded_payload: dict[str, Any]) -> None:
    recorded_payload['_links'] = {'self': {'href': TOUR_URL}}

    tour = Tour(recorded_payload)

    assert tour.links_dict == {'self': {'href': TOUR_URL}}
    assert tour.coordinates_link is None


def test_malformed_embedded_block_is_ignored(recorded_payload: dict[str, Any]) -> None:
    recorded_payload['_embedded'] = ['unexpected']

    tour = Tour(recorded_payload)

    assert tour.creator is None
    assert tour.coordinates == []


def test_string_id_is_converted_to_int(recorded_payload: dict[str, Any]) -> None:
    recorded_payload['id'] = '1000000001'

    assert Tour(recorded_payload).id == 1000000001


def test_missing_id_raises_key_error(recorded_payload: dict[str, Any]) -> None:
    del recorded_payload['id']

    with pytest.raises(KeyError):
        Tour(recorded_payload)


def test_non_numeric_id_raises_value_error(recorded_payload: dict[str, Any]) -> None:
    recorded_payload['id'] = 'abc'

    with pytest.raises(ValueError, match='abc'):
        Tour(recorded_payload)


def test_summary_and_information_from_dict_tolerate_missing_lists() -> None:
    assert TourSummary.from_dict({}) == TourSummary(surfaces=[], way_types=[])
    assert TourInformation.from_dict({'type': 'OFF_GRID'}) == TourInformation('OFF_GRID', [])


# --------------------------------------------------------------------------- deprecated generate_coordinates


def test_generate_coordinates(
    recorded_tour: Tour,
    mocked_responses: responses.RequestsMock,
    logged_in_authentication: Authentication,
    api_fixture: Callable[[str], Any],
) -> None:
    mocked_responses.get(
        COORDINATES_URL,
        json=api_fixture('tour_coordinates'),
        match=[responses.matchers.header_matcher({'Authorization': _basic_auth_header('1234567890', 'TOKEN')})],
    )

    with pytest.warns(DeprecationWarning, match=r'get_tour_coordinates'):
        result = recorded_tour.generate_coordinates(logged_in_authentication)

    assert result is True
    assert recorded_tour.coordinates == [
        Coordinate(46.002331, 8.002309, 578.4, 0),
        Coordinate(46.002188, 8.004596, 578.4, 2000),
        Coordinate(46.002898, 8.000215, 578.4, 5000),
    ]


def test_generate_coordinates_without_links_builds_the_url(
    recorded_payload: dict[str, Any],
    mocked_responses: responses.RequestsMock,
    logged_in_authentication: Authentication,
) -> None:
    del recorded_payload['_links']
    tour = Tour(recorded_payload)
    mocked_responses.get(COORDINATES_URL, json={'items': [{'lat': 1, 'lng': 2}]})

    with pytest.warns(DeprecationWarning, match='is deprecated'):
        assert tour.generate_coordinates(logged_in_authentication) is True

    assert tour.coordinates == [Coordinate(1, 2)]


def test_generate_coordinates_before_login_uses_email_and_password(
    recorded_tour: Tour, mocked_responses: responses.RequestsMock
) -> None:
    authentication = Authentication(email_address='user@example.com', password='secret-password')
    mocked_responses.get(
        COORDINATES_URL,
        json={'items': []},
        match=[
            responses.matchers.header_matcher(
                {'Authorization': _basic_auth_header('user@example.com', 'secret-password')}
            )
        ],
    )

    with pytest.warns(DeprecationWarning, match='is deprecated'):
        assert recorded_tour.generate_coordinates(authentication) is True

    assert recorded_tour.coordinates == []


@pytest.mark.parametrize(
    ('status', 'exception'),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (404, NotFoundError),
        (429, RateLimitError),
        (500, ServerError),
        (503, ServerError),
        (418, KomootAPIError),
    ],
)
def test_generate_coordinates_maps_http_errors(
    recorded_tour: Tour,
    mocked_responses: responses.RequestsMock,
    logged_in_authentication: Authentication,
    status: int,
    exception: type[KomootAPIError],
) -> None:
    mocked_responses.get(COORDINATES_URL, status=status, json={'error': 'nope'})

    with pytest.warns(DeprecationWarning, match='is deprecated'), pytest.raises(exception) as error_info:
        recorded_tour.generate_coordinates(logged_in_authentication)

    assert error_info.value.status_code == status
    assert error_info.value.url == COORDINATES_URL
    assert 'nope' in error_info.value.body
    assert recorded_tour.coordinates == []


def test_authentication_error_is_still_a_connection_error(
    recorded_tour: Tour, mocked_responses: responses.RequestsMock, logged_in_authentication: Authentication
) -> None:
    mocked_responses.get(COORDINATES_URL, status=401)

    with pytest.warns(DeprecationWarning, match='is deprecated'), pytest.raises(ConnectionError):
        recorded_tour.generate_coordinates(logged_in_authentication)


@pytest.mark.parametrize(
    ('header', 'expected'),
    [('12', 12.0), ('Wed, 21 Oct 2015 07:28:00 GMT', 0.0), ('soon', None), (None, None)],
)
def test_rate_limit_error_carries_retry_after(
    recorded_tour: Tour,
    mocked_responses: responses.RequestsMock,
    logged_in_authentication: Authentication,
    header: str | None,
    expected: float | None,
) -> None:
    headers = {} if header is None else {'Retry-After': header}
    mocked_responses.get(COORDINATES_URL, status=429, headers=headers)

    with pytest.warns(DeprecationWarning, match='is deprecated'), pytest.raises(RateLimitError) as error_info:
        recorded_tour.generate_coordinates(logged_in_authentication)

    assert error_info.value.retry_after == expected


@pytest.mark.parametrize('body', ['not json', '{"no_items": []}', '[1, 2]'])
def test_generate_coordinates_unexpected_payload(
    recorded_tour: Tour,
    mocked_responses: responses.RequestsMock,
    logged_in_authentication: Authentication,
    body: str,
) -> None:
    mocked_responses.get(COORDINATES_URL, body=body)

    with pytest.warns(DeprecationWarning, match='is deprecated'), pytest.raises(KomootResponseError):
        recorded_tour.generate_coordinates(logged_in_authentication)


@pytest.mark.parametrize(
    ('error', 'exception'),
    [
        (requests.ConnectionError('offline'), KomootConnectionError),
        (requests.ConnectTimeout('slow'), KomootTimeoutError),
        (requests.ReadTimeout('slow'), KomootTimeoutError),
    ],
)
def test_generate_coordinates_network_failures(
    recorded_tour: Tour,
    mocked_responses: responses.RequestsMock,
    logged_in_authentication: Authentication,
    error: Exception,
    exception: type[Exception],
) -> None:
    mocked_responses.get(COORDINATES_URL, body=error)

    with pytest.warns(DeprecationWarning, match='is deprecated'), pytest.raises(exception) as error_info:
        recorded_tour.generate_coordinates(logged_in_authentication)

    assert error_info.value.__cause__ is error
    assert isinstance(error_info.value, ConnectionError)


# --------------------------------------------------------------------------- deprecated generate_gpx_track


def test_generate_gpx_track(
    recorded_tour: Tour, mocked_responses: responses.RequestsMock, logged_in_authentication: Authentication
) -> None:
    mocked_responses.get(
        GPX_URL,
        body=EXAMPLE_GPX.read_text(encoding='utf-8'),
        content_type='application/gpx+xml',
        match=[
            responses.matchers.header_matcher({'Accept': 'application/gpx+xml', 'User-Agent': USER_AGENT}),
            responses.matchers.query_string_matcher(''),
        ],
    )

    with pytest.warns(DeprecationWarning, match=r'get_tour_gpx'):
        result = recorded_tour.generate_gpx_track(logged_in_authentication)

    assert result is True
    assert isinstance(recorded_tour.gpx_track, GPX)
    assert recorded_tour.gpx_track.get_track_points_no() > 0


def test_generate_gpx_track_invalid_body(
    recorded_tour: Tour, mocked_responses: responses.RequestsMock, logged_in_authentication: Authentication
) -> None:
    mocked_responses.get(GPX_URL, body='<html>definitely not gpx')

    with pytest.warns(DeprecationWarning, match='is deprecated'), pytest.raises(KomootResponseError):
        recorded_tour.generate_gpx_track(logged_in_authentication)

    assert recorded_tour.gpx_track is None


@pytest.mark.parametrize(
    ('status', 'exception'), [(401, AuthenticationError), (404, NotFoundError), (500, ServerError)]
)
def test_generate_gpx_track_maps_http_errors(
    recorded_tour: Tour,
    mocked_responses: responses.RequestsMock,
    logged_in_authentication: Authentication,
    status: int,
    exception: type[KomootAPIError],
) -> None:
    mocked_responses.get(GPX_URL, status=status, body='<error/>')

    with pytest.warns(DeprecationWarning, match='is deprecated'), pytest.raises(exception):
        recorded_tour.generate_gpx_track(logged_in_authentication)

    assert recorded_tour.gpx_track is None


# ----------------------------------------------------------------- JSON null in required nested values


def test_null_required_values_do_not_become_the_string_none() -> None:
    tour = Tour(
        {
            'id': 1,
            'difficulty': {'grade': None},
            'map_image': {'src': None},
            '_embedded': {'creator': {'username': None}},
        }
    )

    assert tour.difficulty is None
    assert tour.map_image is None
    assert tour.creator is None


@pytest.mark.parametrize('tour_id', [True, 12.7, None, 'abc'])
def test_invalid_ids_are_rejected_instead_of_truncated(tour_id: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        Tour({'id': tour_id})
