"""Users and highlights."""

from __future__ import annotations

import logging

import pytest
import responses

from kompy import Highlight, KomootConnector, User
from kompy.exceptions import KomootResponseError, NotFoundError
from tests.conftest import API, USERNAME, query_of, read_api_fixture

HIGHLIGHTS_URL = f'{API}/users/{USERNAME}/highlights/'


# ----------------------------------------------------------------- users


def test_get_own_user(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/users/{USERNAME}/', json=read_api_fixture('user'))

    user = connector.get_user()

    assert isinstance(user, User)
    assert user.username == USERNAME
    assert user.locale == 'en_US'


def test_get_own_user_by_name(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/users/{USERNAME}/', json=read_api_fixture('user'))

    assert connector.get_user(USERNAME).display_name == 'Sample display_name'


def test_get_other_user_uses_public_profile(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    payload = read_api_fixture('user_profile_embedded')
    payload['username'] = 'someone'
    mocked_responses.get(f'{API}/users/someone/profile_embedded', json=payload)

    user = connector.get_user('someone')

    assert user.username == 'someone'
    assert user.is_premium is False


def test_get_user_not_found(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/users/nobody/profile_embedded', status=404)

    with pytest.raises(NotFoundError):
        connector.get_user('nobody')


def test_get_user_unparseable(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/users/{USERNAME}/', json={'display_name': 'no username'})

    with pytest.raises(KomootResponseError, match='could not be parsed'):
        connector.get_user()


# ----------------------------------------------------------------- highlights


def test_get_user_highlights(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(HIGHLIGHTS_URL, json=read_api_fixture('user_highlights'))

    highlights = connector.get_user_highlights()

    assert len(highlights) == 1
    assert isinstance(highlights[0], Highlight)
    assert query_of(mocked_responses.calls[1].request) == {'limit': ['100'], 'page': ['0']}


def test_get_user_highlights_paginates_with_limit(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    item = read_api_fixture('user_highlights')['_embedded']['items'][0]
    first = {'_embedded': {'items': [{**item, 'id': 1}, {**item, 'id': 2}]}, 'page': {'number': 0, 'totalPages': 3}}
    second = {'_embedded': {'items': [{**item, 'id': 3}, {**item, 'id': 4}]}, 'page': {'number': 1, 'totalPages': 3}}
    mocked_responses.get(f'{API}/users/someone/highlights/', json=first)
    mocked_responses.get(f'{API}/users/someone/highlights/', json=second)

    highlights = connector.get_user_highlights('someone', limit=3, page_size=2)

    assert [highlight.id for highlight in highlights] == [1, 2, 3]
    assert [query_of(call.request)['page'] for call in mocked_responses.calls[1:]] == [['0'], ['1']]


def test_iter_user_highlights_limit_sets_page_size(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(HIGHLIGHTS_URL, json=read_api_fixture('user_highlights'))

    assert len(list(connector.iter_user_highlights(limit=5))) == 1
    assert query_of(mocked_responses.calls[1].request)['limit'] == ['5']


@pytest.mark.parametrize('item', [{'name': 'no id'}, {'id': 'abc'}, {'id': None}, None, 'garbage', 42, [1]])
def test_user_highlights_skip_unparseable(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture, item: object
) -> None:
    payload = read_api_fixture('user_highlights')
    payload['_embedded']['items'].append(item)
    mocked_responses.get(HIGHLIGHTS_URL, json=payload)

    with caplog.at_level(logging.WARNING, logger='kompy'):
        assert len(connector.get_user_highlights()) == 1

    assert 'Skipping a highlight' in caplog.text


def test_user_highlights_empty(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(HIGHLIGHTS_URL, json={'page': {'number': 0, 'totalPages': 0}})

    assert connector.get_user_highlights() == []


@pytest.mark.parametrize(('limit', 'page_size', 'match'), [(-1, None, 'limit'), (None, 0, 'page_size')])
def test_user_highlights_invalid_arguments(
    connector: KomootConnector, limit: int | None, page_size: int | None, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        connector.iter_user_highlights(limit=limit, page_size=page_size)


def test_get_highlight(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/highlights/85124', json=read_api_fixture('highlight'))

    highlight = connector.get_highlight(85124)

    assert highlight.id == 85124
    assert highlight.type == 'highlight_segment'


def test_get_highlight_unparseable(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/highlights/1', json={'id': 'not a number'})

    with pytest.raises(KomootResponseError, match='highlight 1 could not be parsed'):
        connector.get_highlight(1)
