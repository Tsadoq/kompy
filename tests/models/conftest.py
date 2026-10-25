"""Fixtures shared by the model tests."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
import responses

from kompy import Authentication
from tests.models._api import read_api_fixture


@pytest.fixture
def api_fixture() -> Callable[[str], Any]:
    """Return a loader for the anonymized API payloads (a fresh copy on every call)."""
    return read_api_fixture


@pytest.fixture
def mocked_responses() -> Iterator[responses.RequestsMock]:
    """Activate ``responses``: unmatched requests fail, and every registered response must be used."""
    with responses.RequestsMock(assert_all_requests_are_fired=True) as mock:
        yield mock


@pytest.fixture
def logged_in_authentication() -> Authentication:
    """An Authentication object in the state a successful login leaves it in."""
    authentication = Authentication(email_address='user@example.com', password='secret-password')
    authentication.set_username('1234567890')
    authentication.set_token('TOKEN')
    return authentication
