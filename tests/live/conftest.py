"""
Fixtures of the live contract tests, which talk to the real Komoot API.

They run only with ``pytest -m live`` and are skipped unless ``KOMOOT_EMAIL`` and ``KOMOOT_PASSWORD`` are set; with
``KOMOOT_LIVE_REQUIRED=1`` (set by the scheduled workflow) missing credentials fail the run instead, so a contract
check that tests nothing never looks green. Tests that create, change and delete tours additionally need
``KOMOOT_LIVE_WRITE=1``. Use a dedicated test account.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import pytest
import requests

from kompy import KomootConnector, Tour
from kompy.constants import TourTypes

LIVE_PAGE_SIZE = 100


@dataclass
class CallLog:
    """Every HTTP exchange of the shared connector, as ``(method, path, status)``."""

    calls: list[tuple[str, str, int]] = field(default_factory=list)

    def hook(self, response: requests.Response, *_args: Any, **_kwargs: Any) -> None:
        request = response.request
        path = urlsplit(response.url).path
        self.calls.append((str(request.method), path, response.status_code))

    def mark(self) -> int:
        return len(self.calls)

    def since(self, mark: int) -> list[tuple[str, str, int]]:
        return self.calls[mark:]


def _credentials() -> tuple[str, str]:
    email, password = os.environ.get('KOMOOT_EMAIL'), os.environ.get('KOMOOT_PASSWORD')
    if not email or not password:
        message = 'KOMOOT_EMAIL and KOMOOT_PASSWORD are not set.'
        if os.environ.get('KOMOOT_LIVE_REQUIRED') == '1':
            pytest.fail(f'{message} KOMOOT_LIVE_REQUIRED=1 forbids skipping the live tests.')
        pytest.skip(message)
    return email, password


@pytest.fixture(scope='session')
def credentials() -> tuple[str, str]:
    """The email address and password of the test account (skips the test when missing)."""
    return _credentials()


@pytest.fixture(scope='session')
def call_log() -> CallLog:
    """Log of the HTTP exchanges of :func:`live_connector`."""
    return CallLog()


@pytest.fixture(scope='session')
def live_connector(credentials: tuple[str, str], call_log: CallLog) -> Iterator[KomootConnector]:
    """One logged-in connector shared by all live tests, to keep the number of logins low."""
    session = requests.Session()
    session.hooks['response'].append(call_log.hook)
    with KomootConnector(*credentials, session=session) as connector:
        yield connector
    session.close()


@pytest.fixture(scope='session')
def first_page(live_connector: KomootConnector) -> list[Tour]:
    """The first page of the account's tours."""
    tours = live_connector.get_tours(page=0, page_size=LIVE_PAGE_SIZE)
    if not tours:
        pytest.skip('The test account has no tours.')
    return tours


def require_tours(first_page: list[Tour], count: int) -> None:
    """Skip a test that needs at least ``count`` tours on the test account (a small account is not an API change)."""
    if len(first_page) < count:
        pytest.skip(f'The test account needs at least {count} tours, it has {len(first_page)}.')


def _find(live_connector: KomootConnector, first_page: list[Tour], tour_type: str) -> Tour:
    for tour in first_page:
        if tour.type == tour_type:
            return tour
    found = live_connector.get_tours(limit=1, tour_type=tour_type)
    if not found:
        pytest.skip(f'The test account has no {tour_type} tour.')
    return found[0]


@pytest.fixture(scope='session')
def recorded_tour(live_connector: KomootConnector, first_page: list[Tour]) -> Tour:
    """A recorded tour of the account."""
    return _find(live_connector, first_page, TourTypes.TOUR_RECORDED)


@pytest.fixture(scope='session')
def planned_tour(live_connector: KomootConnector, first_page: list[Tour]) -> Tour:
    """A planned tour of the account."""
    return _find(live_connector, first_page, TourTypes.TOUR_PLANNED)


@pytest.fixture
def write_enabled() -> None:
    """Skip tests that change the account unless ``KOMOOT_LIVE_WRITE=1``."""
    if os.environ.get('KOMOOT_LIVE_WRITE') != '1':
        pytest.skip('Set KOMOOT_LIVE_WRITE=1 to run the live tests that create and delete tours.')
