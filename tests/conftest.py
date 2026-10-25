"""
Fixtures shared by the whole test suite.

Real network access is blocked in every test that is not marked ``live``: HTTP calls must be mocked with
``responses`` (see the ``mocked_responses`` fixture).
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses

from kompy import KomootConnector

API_FIXTURES = Path(__file__).parent / 'resources' / 'api'
EXAMPLE_GPX = Path(__file__).parent / 'resources' / 'example.gpx'

EMAIL = 'user@example.com'
PASSWORD = 'secret-password'
USERNAME = '1234567890'
TOKEN = 'TOKEN'
LOGIN_URL = f'https://api.komoot.de/v006/account/email/{EMAIL}/'
API = 'https://api.komoot.de/v007'


def read_api_fixture(name: str) -> Any:
    """
    Load an anonymized API payload from ``tests/resources/api``.

    :param name: File name without the ``.json`` suffix.
    :return: The decoded payload (a fresh copy on every call).
    """
    return json.loads((API_FIXTURES / f'{name}.json').read_text(encoding='utf-8'))


def query_of(request: Any) -> dict[str, list[str]]:
    """
    Decode the query string of a request recorded by ``responses``.

    :param request: ``responses.calls[i].request``.
    :return: Each parameter with the list of its values.
    """
    return parse_qs(urlsplit(request.url).query, keep_blank_values=True)


def sent_timeout(request: Any) -> Any:
    """
    Get the timeout a request recorded by ``responses`` was sent with.

    :param request: ``responses.calls[i].request``.
    :return: The ``timeout`` argument given to ``requests``.
    """
    return request.req_kwargs['timeout']


def json_body(request: Any) -> Any:
    """
    Decode the JSON body of a request recorded by ``responses``.

    :param request: ``responses.calls[i].request``.
    :return: The decoded body.
    """
    return json.loads(request.body)


def tour_page(tours: list[Any], *, number: int = 0, total_pages: int = 1) -> dict[str, Any]:
    """
    Build a page of the tour list endpoint around the given tours (an empty list gives an empty HAL page).

    :param tours: The tour payloads of the page.
    :param number: The page index.
    :param total_pages: The total number of pages.
    :return: The page payload.
    """
    page: dict[str, Any] = {
        '_links': {'self': {'href': f'{API}/users/{USERNAME}/tours/'}},
        'page': {'size': max(len(tours), 1), 'totalElements': 0, 'totalPages': total_pages, 'number': number},
    }
    if tours:
        page['_embedded'] = {'tours': tours}
    return page


def make_tour(tour_id: object, **changes: Any) -> dict[str, Any]:
    """
    Build a listed tour payload from the real fixture, with another id and optional field changes.

    :param tour_id: The id of the tour.
    :param changes: Fields to override.
    :return: The tour payload.
    """
    tour: dict[str, Any] = copy.deepcopy(read_api_fixture('tours_list_page')['_embedded']['tours'][0])
    tour['id'] = tour_id
    tour.update(changes)
    return tour


LOCALHOST = '127.0.0.1'
"""The only host unit tests may really connect to (see ``tests/test_http_transport.py``)."""


@pytest.fixture(autouse=True)
def _block_real_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Fail any HTTP request that is not intercepted by ``responses`` (except in ``live`` tests).

    Requests to a local test server on ``127.0.0.1`` are let through, so the real urllib3 transport (timeouts,
    retries, ``Retry-After``) can be tested.
    """
    if request.node.get_closest_marker('live') is not None:
        return
    send = requests.adapters.HTTPAdapter.send

    def refuse(adapter: requests.adapters.HTTPAdapter, prepared: Any, *args: Any, **kwargs: Any) -> requests.Response:
        if urlsplit(prepared.url).hostname == LOCALHOST:
            return send(adapter, prepared, *args, **kwargs)
        raise RuntimeError('Real network access is not allowed in unit tests; mock the request with responses.')

    monkeypatch.setattr(requests.adapters.HTTPAdapter, 'send', refuse)


@pytest.fixture
def load_api_fixture() -> Callable[[str], Any]:
    """Return a loader for the anonymized API payloads (a fresh copy on every call)."""
    return read_api_fixture


@pytest.fixture
def mocked_responses() -> Iterator[responses.RequestsMock]:
    """Activate ``responses``: unmatched requests fail, and every registered response must be used."""
    with responses.RequestsMock(assert_all_requests_are_fired=True) as mock:
        yield mock


def register_login(mock: responses.RequestsMock, **kwargs: Any) -> None:
    """
    Register a successful login response.

    :param mock: The active ``responses`` mock.
    :param kwargs: Overrides for ``mock.get`` (e.g. ``status`` or ``json``).
    """
    options: dict[str, Any] = {'json': read_api_fixture('login'), 'status': 200}
    options.update(kwargs)
    mock.get(LOGIN_URL, **options)


@pytest.fixture
def connector(mocked_responses: responses.RequestsMock) -> Iterator[KomootConnector]:
    """A connector logged in through a mocked login, without retries; the login call is ``responses.calls[0]``."""
    register_login(mocked_responses)
    with KomootConnector(EMAIL, PASSWORD, max_retries=0) as logged_in:
        yield logged_in
