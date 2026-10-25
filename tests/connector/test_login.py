"""Login, token authentication and connector lifecycle."""

from __future__ import annotations

import base64
from typing import Any

import pytest
import requests
import responses

from kompy import KomootConnector
from kompy.errors.initialisation_errors import NotEmailError
from kompy.exceptions import AuthenticationError, KomootConnectionError, KomootResponseError, ServerError
from tests.conftest import (
    API,
    EMAIL,
    LOGIN_URL,
    PASSWORD,
    TOKEN,
    USERNAME,
    read_api_fixture,
    register_login,
    sent_timeout,
)

PROFILE_URL = f'{API}/users/{USERNAME}/profile_embedded'


def basic(user: str, password: str) -> str:
    return 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()


# ----------------------------------------------------------------- login


def test_login_stores_username_and_token(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    login = mocked_responses.calls[0].request

    assert login.url == LOGIN_URL
    assert login.headers['Authorization'] == basic(EMAIL, PASSWORD)
    assert connector.username == USERNAME
    assert connector.token == TOKEN
    assert connector.authentication.get_username() == USERNAME
    assert connector.authentication.get_token() == TOKEN


def test_requests_after_login_use_the_token(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(f'{API}/tours/1', json=read_api_fixture('tour_recorded_by_id'))

    connector.get_tour_by_id(1)

    headers = mocked_responses.calls[1].request.headers
    assert headers['Authorization'] == basic(USERNAME, TOKEN)
    assert PASSWORD not in base64.b64decode(headers['Authorization'].removeprefix('Basic ')).decode()


def test_user_agent_is_sent(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    assert mocked_responses.calls[0].request.headers['User-Agent'].startswith('kompy/')


def test_email_is_quoted_in_login_url(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(
        'https://api.komoot.de/v006/account/email/a%23b%2Bc@example.com/', json=read_api_fixture('login')
    )

    KomootConnector('a#b+c@example.com', PASSWORD, max_retries=0).close()

    assert len(mocked_responses.calls) == 1


@pytest.mark.parametrize('email', ['not-an-email', '', 'user.example.com'])
def test_invalid_email_is_rejected_without_request(mocked_responses: responses.RequestsMock, email: str) -> None:
    with pytest.raises(NotEmailError):
        KomootConnector(email, PASSWORD)


@pytest.mark.parametrize('status', [401, 403])
def test_rejected_credentials(mocked_responses: responses.RequestsMock, status: int) -> None:
    body = {'error': 'BadCredentials', 'code': status, 'message': 'Unknown user or wrong credentials.'}
    register_login(mocked_responses, status=status, json=body)

    with pytest.raises(AuthenticationError, match='rejected the email address or password') as caught:
        KomootConnector(EMAIL, PASSWORD)

    assert isinstance(caught.value, ConnectionError)  # what older kompy versions raised
    assert caught.value.status_code == status
    assert isinstance(caught.value.__cause__, AuthenticationError)


def test_login_server_error(mocked_responses: responses.RequestsMock) -> None:
    register_login(mocked_responses, status=500, json=None, body='<html>oops</html>')

    with pytest.raises(ServerError):
        KomootConnector(EMAIL, PASSWORD, max_retries=0)


def test_login_network_error(mocked_responses: responses.RequestsMock) -> None:
    register_login(mocked_responses, json=None, body=requests.ConnectionError('offline'))

    with pytest.raises(KomootConnectionError):
        KomootConnector(EMAIL, PASSWORD, max_retries=0)


@pytest.mark.parametrize('payload', [{'username': USERNAME}, {'password': TOKEN}, {}])
def test_login_response_without_username_or_token(
    mocked_responses: responses.RequestsMock, payload: dict[str, Any]
) -> None:
    register_login(mocked_responses, json=payload)

    with pytest.raises(KomootResponseError, match='username or token'):
        KomootConnector(EMAIL, PASSWORD)


def test_failed_login_closes_the_session(
    mocked_responses: responses.RequestsMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[bool] = []
    monkeypatch.setattr(requests.Session, 'close', lambda _self: closed.append(True))
    register_login(mocked_responses, status=403, json={})

    with pytest.raises(AuthenticationError):
        KomootConnector(EMAIL, PASSWORD)

    assert closed == [True]


def test_rejected_token_after_login(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/tours/1', status=401, json={'error': 'BadCredentials'})

    with pytest.raises(AuthenticationError, match='rejected the token') as caught:
        connector.get_tour_by_id(1)

    assert caught.value.status_code == 401


def test_forbidden_is_not_reported_as_rejected_token(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(f'{API}/tours/1', status=403)

    with pytest.raises(AuthenticationError, match='denied access'):
        connector.get_tour_by_id(1)


# ----------------------------------------------------------------- from_token


def test_from_token_sends_no_login(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/tours/1', json=read_api_fixture('tour_recorded_by_id'))

    with KomootConnector.from_token(USERNAME, TOKEN) as connector:
        connector.get_tour_by_id(1)

    assert len(mocked_responses.calls) == 1
    assert mocked_responses.calls[0].request.headers['Authorization'] == basic(USERNAME, TOKEN)
    assert connector.username == USERNAME
    assert connector.token == TOKEN


def test_from_token_validate(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(PROFILE_URL, json=read_api_fixture('user_profile_embedded'))

    KomootConnector.from_token(USERNAME, TOKEN, validate=True).close()

    assert mocked_responses.calls[0].request.url == PROFILE_URL


def test_from_token_validate_rejected(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(PROFILE_URL, status=401)

    with pytest.raises(AuthenticationError, match=r'rejected the token \(revoked or invalid\)\. Log in again'):
        KomootConnector.from_token(USERNAME, TOKEN, validate=True)


@pytest.mark.parametrize(('username', 'token'), [('', TOKEN), (USERNAME, '')])
def test_from_token_rejects_empty_values(username: str, token: str) -> None:
    with pytest.raises(ValueError, match='cannot be empty'):
        KomootConnector.from_token(username, token)


# ----------------------------------------------------------------- from_env


def test_from_env_prefers_token(mocked_responses: responses.RequestsMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('KOMOOT_USERNAME', USERNAME)
    monkeypatch.setenv('KOMOOT_TOKEN', TOKEN)
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', PASSWORD)

    connector = KomootConnector.from_env()

    assert connector.token == TOKEN
    assert len(mocked_responses.calls) == 0  # no login


def test_from_env_with_email_and_password(
    mocked_responses: responses.RequestsMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv('KOMOOT_USERNAME', raising=False)
    monkeypatch.setenv('KOMOOT_TOKEN', TOKEN)  # incomplete token pair: ignored
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', PASSWORD)
    register_login(mocked_responses)

    with KomootConnector.from_env(max_retries=0, timeout=3) as connector:
        assert connector.username == USERNAME

    assert sent_timeout(mocked_responses.calls[0].request) == 3


def test_from_env_custom_prefix(mocked_responses: responses.RequestsMock, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MY_EMAIL', EMAIL)
    monkeypatch.setenv('MY_PASSWORD', PASSWORD)
    register_login(mocked_responses)

    assert KomootConnector.from_env(prefix='MY_').username == USERNAME


def test_from_env_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ('USERNAME', 'TOKEN', 'EMAIL', 'PASSWORD'):
        monkeypatch.delenv(f'KOMOOT_{name}', raising=False)
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)  # password missing

    with pytest.raises(ValueError, match='KOMOOT_EMAIL and KOMOOT_PASSWORD'):
        KomootConnector.from_env()


# ----------------------------------------------------------------- lifecycle


def test_context_manager_closes_session(
    mocked_responses: responses.RequestsMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed: list[bool] = []
    monkeypatch.setattr(requests.Session, 'close', lambda _self: closed.append(True))
    register_login(mocked_responses)

    with KomootConnector(EMAIL, PASSWORD) as connector:
        assert closed == []

    assert closed == [True]
    assert isinstance(connector, KomootConnector)


def test_provided_session_is_used_and_left_open(mocked_responses: responses.RequestsMock) -> None:
    session = requests.Session()
    closed: list[bool] = []
    session.close = lambda: closed.append(True)  # type: ignore[method-assign]
    register_login(mocked_responses)

    with KomootConnector(EMAIL, PASSWORD, session=session):
        pass

    assert closed == []


def test_repr_has_no_secrets(connector: KomootConnector) -> None:
    text = repr(connector)

    assert text == f"KomootConnector(username='{USERNAME}')"
    assert PASSWORD not in text
    assert TOKEN not in text
    assert PASSWORD not in repr(connector.authentication)
