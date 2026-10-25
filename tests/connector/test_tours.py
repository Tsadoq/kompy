"""Listing tours: ``get_tours`` and ``iter_tours``."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

import pytest
import responses

from kompy import KomootConnector, Tour
from kompy.constants import PrivacyStatus, SupportedActivities, TourSort, TourSortField, TourTypes
from kompy.constants.query_parameters import TourQueryParameters, format_api_datetime
from kompy.errors.privacy_errors import PrivacyError
from kompy.exceptions import KomootResponseError, NotFoundError, RateLimitError
from kompy.komoot_connector import FILTERED_PAGE_SIZE
from tests.conftest import API, USERNAME, make_tour, query_of, read_api_fixture, tour_page

TOURS_URL = f'{API}/users/{USERNAME}/tours/'
OTHER_URL = f'{API}/users/someone/tours/'


def list_queries(mock: responses.RequestsMock) -> list[dict[str, list[str]]]:
    """Query strings of the tour list requests (the login call is skipped)."""
    return [query_of(call.request) for call in mock.calls if '/tours/' in str(call.request.url)]


# ----------------------------------------------------------------- basic listing


def test_real_page_is_parsed(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    payload = read_api_fixture('tours_list_page')
    payload['page']['totalPages'] = 1
    mocked_responses.get(TOURS_URL, json=payload)

    tours = connector.get_tours()

    assert [tour.id for tour in tours] == [1000000001, 3359786974, 3357935214]
    assert all(isinstance(tour, Tour) for tour in tours)
    assert list_queries(mocked_responses) == [{'limit': ['100'], 'page': ['0']}]


def test_default_query_has_no_status_and_no_false_flags(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([]))

    connector.get_tours()

    (query,) = list_queries(mocked_responses)
    assert 'status' not in query  # all of the user's own tours, not only the public ones
    assert 'only_unlocked' not in query


def test_empty_result_returns_empty_list(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([], total_pages=0))  # real shape: no "_embedded" key

    assert connector.get_tours() == []


def test_all_pages_are_fetched_without_limit(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1), make_tour(2)], number=0, total_pages=3))
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(3), make_tour(4)], number=1, total_pages=3))
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(5)], number=2, total_pages=3))

    tours = connector.get_tours(page_size=2)

    assert [tour.id for tour in tours] == [1, 2, 3, 4, 5]
    assert [query['page'] for query in list_queries(mocked_responses)] == [['0'], ['1'], ['2']]
    assert {query['limit'][0] for query in list_queries(mocked_responses)} == {'2'}


def test_limit_spans_multiple_pages(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1), make_tour(2)], number=0, total_pages=5))
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(3), make_tour(4)], number=1, total_pages=5))

    tours = connector.get_tours(limit=3, page_size=2)

    assert [tour.id for tour in tours] == [1, 2, 3]
    assert len(list_queries(mocked_responses)) == 2  # page 2 is never requested


def test_limit_sets_the_page_size(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(i) for i in range(10)], total_pages=47))

    tours = connector.get_tours(limit=10)

    assert len(tours) == 10
    assert list_queries(mocked_responses)[0]['limit'] == ['10']


def test_large_limit_uses_pages_of_100(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1)], total_pages=1))

    connector.get_tours(limit=5000)

    assert list_queries(mocked_responses)[0]['limit'] == ['100']


def test_limit_zero_sends_no_request(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    assert connector.get_tours(limit=0) == []
    assert list_queries(mocked_responses) == []


def test_page_is_honoured(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(31), make_tour(32)], number=3, total_pages=10))

    tours = connector.get_tours(page=3, limit=10)

    assert [tour.id for tour in tours] == [31, 32]
    assert list_queries(mocked_responses) == [{'limit': ['10'], 'page': ['3']}]  # exactly that page, nothing more


def test_pagination_falls_back_to_next_link(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    first = {'_embedded': {'tours': [make_tour(1)]}, '_links': {'next': {'href': f'{TOURS_URL}?page=1'}}}
    second = {'_embedded': {'tours': [make_tour(2)]}, '_links': {}}
    mocked_responses.get(TOURS_URL, json=first)
    mocked_responses.get(TOURS_URL, json=second)

    assert [tour.id for tour in connector.get_tours()] == [1, 2]


def test_page_without_number_uses_requested_index(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json={'_embedded': {'tours': [make_tour(1)]}, 'page': {'totalPages': 2}})
    mocked_responses.get(TOURS_URL, json={'_embedded': {'tours': [make_tour(2)]}, 'page': {'totalPages': 2}})

    assert [tour.id for tour in connector.get_tours()] == [1, 2]


def test_page_without_total_and_next_link_is_the_last(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json={'_embedded': {'tours': [make_tour(1)]}, 'page': {'number': 0}})

    assert [tour.id for tour in connector.get_tours()] == [1]


def test_empty_page_stops_pagination(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([], total_pages=99))

    assert connector.get_tours() == []
    assert len(list_queries(mocked_responses)) == 1


def test_iter_tours_is_lazy(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1)], number=0, total_pages=2))
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(2)], number=1, total_pages=2))

    tours = connector.iter_tours(page_size=1)
    assert list_queries(mocked_responses) == []

    assert next(tours).id == 1
    assert len(list_queries(mocked_responses)) == 1
    assert next(tours).id == 2
    assert next(tours, None) is None


def test_iter_tours_validates_eagerly(connector: KomootConnector) -> None:
    with pytest.raises(ValueError, match='tour type'):
        connector.iter_tours(tour_type='nope')


def test_api_errors_propagate(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, status=429, headers={'Retry-After': '30'})

    with pytest.raises(RateLimitError) as caught:
        connector.get_tours()

    assert caught.value.retry_after == 30.0


def test_unknown_user_raises_not_found(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(OTHER_URL, status=404)

    with pytest.raises(NotFoundError):
        connector.get_tours(user_identifier='someone')


# ----------------------------------------------------------------- parsing failures


def test_unknown_sport_is_kept(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1), make_tour(2, sport='UNKNOWN_SPORT_XYZ')]))

    tours = connector.get_tours()

    assert [tour.sport for tour in tours] == [SupportedActivities.RUNNING, 'UNKNOWN_SPORT_XYZ']


def test_unparseable_tours_are_skipped_with_one_warning_each(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture
) -> None:
    no_id = make_tour(2)
    del no_id['id']
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1), no_id, make_tour('abc'), 'garbage']))

    with caplog.at_level(logging.WARNING, logger='kompy'):
        tours = connector.get_tours()

    assert [tour.id for tour in tours] == [1]
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 3
    assert all(record.exc_info is None for record in warnings)  # no traceback spam
    assert 'Skipping tour abc' in warnings[1].getMessage()


def test_all_tours_unparseable_raises(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour('x'), make_tour('y')]))

    with pytest.raises(KomootResponseError, match='Failed to parse all 2') as caught:
        connector.get_tours()

    assert isinstance(caught.value, ValueError)  # what older kompy versions raised


def test_default_calls_log_nothing_above_debug(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1)]))

    with caplog.at_level(logging.DEBUG, logger='kompy'):
        connector.get_tours()

    assert [record for record in caplog.records if record.levelno > logging.INFO] == []


# ----------------------------------------------------------------- status and privacy


def test_status_is_filtered_client_side(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    page = [make_tour(1, status='public'), make_tour(2, status='private'), make_tour(3, status='public')]
    mocked_responses.get(TOURS_URL, json=tour_page(page))

    tours = connector.get_tours(status=PrivacyStatus.PUBLIC)

    assert [tour.id for tour in tours] == [1, 3]
    assert list_queries(mocked_responses)[0]['status'] == ['public']  # still sent


def test_status_filter_with_limit_keeps_paginating(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(
        TOURS_URL, json=tour_page([make_tour(1, status='private'), make_tour(2, status='friends')], total_pages=2)
    )
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(3, status='private')], number=1, total_pages=2))

    tours = connector.get_tours(limit=2, status='private')

    assert [tour.id for tour in tours] == [1, 3]
    assert list_queries(mocked_responses)[0]['limit'] == [str(FILTERED_PAGE_SIZE)]  # large pages: few requests


def test_status_equal_but_not_identical_string(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    status = ''.join(['pub', 'lic'])  # equal to 'public' but a different object
    mocked_responses.get(OTHER_URL, json=tour_page([make_tour(1, status='public')]))

    assert len(connector.get_tours(user_identifier='someone', status=status)) == 1


@pytest.mark.parametrize('status', [PrivacyStatus.PRIVATE, PrivacyStatus.FRIENDS, 'private'])
def test_non_public_tours_of_another_user_raise(connector: KomootConnector, status: str) -> None:
    with pytest.raises(PrivacyError, match='someone'):
        connector.get_tours(user_identifier='someone', status=status)


@pytest.mark.parametrize('status', [PrivacyStatus.PRIVATE, PrivacyStatus.FRIENDS])
def test_own_non_public_tours_are_allowed(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, status: str
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1, status=str(status))]))

    assert len(connector.get_tours(user_identifier=USERNAME, status=status)) == 1


def test_another_users_tours_default_to_public(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(OTHER_URL, json=tour_page([make_tour(1, status='public')]))

    connector.get_tours(user_identifier='someone')

    assert list_queries(mocked_responses)[0]['status'] == ['public']


def test_invalid_status_is_rejected(connector: KomootConnector) -> None:
    with pytest.raises(ValueError, match='Invalid status'):
        connector.get_tours(status='secret')


def test_user_identifier_is_quoted(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/users/a%2Fb/tours/', json=tour_page([]))

    assert connector.get_tours(user_identifier='a/b') == []


# ----------------------------------------------------------------- filters and serialization


def test_all_filters_are_serialized(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([]))

    connector.get_tours(
        tour_type=TourTypes.TOUR_RECORDED,
        only_unlocked=True,
        center='52.520008, 13.404954',
        max_distance=5000,
        sport_types=[SupportedActivities.HIKING, 'mtb'],
        start_date='2023-01-01',
        end_date=datetime(2023, 12, 31, 23, 30, tzinfo=timezone(timedelta(hours=2))),
        tour_name='lake',
        sort=TourSort.ASCENDING,
        sort_field=TourSortField.PROXIMITY,
    )

    assert list_queries(mocked_responses)[0] == {
        'limit': ['100'],
        'page': ['0'],
        'type': ['tour_recorded'],
        'only_unlocked': ['true'],
        'center': ['52.520008,13.404954'],
        'max_distance': ['5000'],
        'sport_types': ['hike,mtb'],
        'start_date': ['2023-01-01T00:00:00.000Z'],
        'end_date': ['2023-12-31T21:30:00.000Z'],
        'name': ['lake'],
        'sort_direction': ['asc'],
        'sort_field': ['proximity'],
    }


def test_max_distance_without_center_is_ignored(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([]))

    with caplog.at_level(logging.WARNING, logger='kompy'):
        connector.get_tours(max_distance=1000)

    assert 'max_distance' not in list_queries(mocked_responses)[0]
    assert 'max_distance is ignored' in caplog.text


def test_unknown_sport_filter_is_sent_with_warning(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([]))

    with caplog.at_level(logging.WARNING, logger='kompy'):
        connector.get_tours(sport_types=('padel',))

    assert list_queries(mocked_responses)[0]['sport_types'] == ['padel']
    assert "Unknown sport 'padel'" in caplog.text


@pytest.mark.parametrize(
    ('kwargs', 'exception', 'match'),
    [
        ({'tour_type': 'tour_dreamed'}, ValueError, 'tour type'),
        ({'center': 'Berlin', 'max_distance': 10}, ValueError, 'Invalid center'),
        ({'center': '52.5,13.4'}, ValueError, 'Max distance must be provided'),
        ({'center': '52.5,13.4', 'max_distance': 0}, ValueError, 'greater than 0'),
        ({'sport_types': 'hike'}, TypeError, 'list of strings'),
        ({'sport_types': ['hike', 3]}, TypeError, 'Please provide a string'),
        ({'start_date': '2024-01-02', 'end_date': '2024-01-01'}, ValueError, 'must be before'),
        ({'start_date': 'yesterday-ish'}, ValueError, 'is not a date'),
        ({'end_date': '99999999999999999999'}, ValueError, 'is not a date'),
        ({'sort': 'sideways'}, ValueError, 'Invalid sort'),
        ({'sort_field': 'colour'}, ValueError, 'Invalid sort_field'),
        ({'sort_field': 'proximity'}, ValueError, 'requires a center'),
        ({'limit': -1}, ValueError, 'limit must be 0 or greater'),
        ({'page': -1}, ValueError, 'page must be 0 or greater'),
        ({'page_size': 0}, ValueError, 'page_size'),
    ],
)
def test_invalid_arguments_raise_before_any_request(
    connector: KomootConnector,
    mocked_responses: responses.RequestsMock,
    kwargs: dict[str, Any],
    exception: type[Exception],
    match: str,
) -> None:
    with pytest.raises(exception, match=match):
        connector.get_tours(**kwargs)

    assert list_queries(mocked_responses) == []


def test_dates_accept_date_and_mixed_timezones(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([]))

    connector.get_tours(start_date=date(2023, 5, 1), end_date='2023-05-01T10:00:00+02:00')

    query = list_queries(mocked_responses)[0]
    assert query['start_date'] == ['2023-05-01T00:00:00.000Z']
    assert query['end_date'] == ['2023-05-01T08:00:00.000Z']


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (date(2023, 1, 2), '2023-01-02T00:00:00.000Z'),
        (datetime(2023, 1, 2, 3, 4, 5, 678901), '2023-01-02T03:04:05.678Z'),
        (datetime(2023, 1, 2, 3, 4, 5, tzinfo=UTC), '2023-01-02T03:04:05.000Z'),
        (datetime(2023, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-5))), '2023-01-02T08:04:05.000Z'),
    ],
)
def test_format_api_datetime(value: date, expected: str) -> None:
    assert format_api_datetime(value) == expected


def test_construct_tour_query_drops_none_and_keeps_strings() -> None:
    query = TourQueryParameters.construct_tour_query(
        limit=5, only_unlocked=False, start_date='2020-01-01', status=PrivacyStatus.PUBLIC, sport_types=[]
    )

    assert query == {'limit': 5, 'start_date': '2020-01-01', 'status': 'public'}
    assert type(query['status']) is str


# ----------------------------------------------------------------- page windows


def test_page_with_limit_above_100_is_one_page_of_limit_tours(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(i) for i in range(250)], total_pages=6))

    tours = connector.get_tours(page=0, limit=250)

    assert len(tours) == 250  # not silently capped at 100
    assert list_queries(mocked_responses) == [{'limit': ['250'], 'page': ['0']}]


def test_status_filter_does_not_change_the_page_window(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    page = [make_tour(20 + i, status='private' if i % 2 else 'friends') for i in range(10)]
    mocked_responses.get(TOURS_URL, json=tour_page(page, number=2, total_pages=10))

    tours = connector.get_tours(page=2, limit=10, status=PrivacyStatus.PRIVATE)

    assert [tour.id for tour in tours] == [21, 23, 25, 27, 29]  # tours 20-29, filtered afterwards
    assert list_queries(mocked_responses) == [{'limit': ['10'], 'status': ['private'], 'page': ['2']}]


def test_page_without_limit_uses_the_default_page_size(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1)], number=1, total_pages=2))

    connector.get_tours(page=1, status='friends')

    assert list_queries(mocked_responses)[0]['limit'] == ['100']


def test_explicit_page_size_wins_over_limit_for_a_page(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(i) for i in range(20)], number=1, total_pages=3))

    tours = connector.get_tours(page=1, limit=5, page_size=20)

    assert len(tours) == 5
    assert list_queries(mocked_responses)[0]['limit'] == ['20']


# ----------------------------------------------------------------- a Tour instead of an id


def test_get_tour_by_id_accepts_a_tour(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    tour = Tour(make_tour(1000000001))
    mocked_responses.get(f'{API}/tours/1000000001', json=make_tour(1000000001))

    assert connector.get_tour_by_id(tour).id == 1000000001
    assert mocked_responses.calls[1].request.url.endswith('/tours/1000000001')
