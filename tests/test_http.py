"""Tests for the private HTTP layer, :mod:`kompy._http`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import pytest
import requests
import responses

from kompy import __version__
from kompy._http import (
    DEFAULT_TIMEOUT,
    MAX_RETRY_AFTER,
    USER_AGENT,
    HttpClient,
    _KompyRetry,
    build_url,
    decode_json_object,
    parse_retry_after,
    redact,
)
from kompy.exceptions import (
    AuthenticationError,
    KomootAPIError,
    KomootConnectionError,
    KomootResponseError,
    KomootTimeoutError,
    NotFoundError,
    RateLimitError,
    ServerError,
)
from tests.conftest import sent_timeout

URL = 'https://api.komoot.de/v007/thing'


@pytest.fixture
def client() -> HttpClient:
    """A client without retries."""
    return HttpClient(max_retries=0)


# ----------------------------------------------------------------- build_url


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('user@example.com', 'user@example.com'),
        ('a#b@example.com', 'a%23b@example.com'),
        ('a?b@example.com', 'a%3Fb@example.com'),
        ('a/b@example.com', 'a%2Fb@example.com'),
        ('a+b@example.com', 'a%2Bb@example.com'),
        ('a%b@example.com', 'a%25b@example.com'),
        ('../admin', '..%2Fadmin'),
        (12345, '12345'),
    ],
)
def test_build_url_quotes_path_segments(value: object, expected: str) -> None:
    assert build_url('https://x/{segment}/', segment=value) == f'https://x/{expected}/'


# ----------------------------------------------------------------- status mapping


@pytest.mark.parametrize(
    ('status', 'exception', 'builtin'),
    [
        (400, KomootAPIError, None),
        (401, AuthenticationError, ConnectionError),
        (403, AuthenticationError, ConnectionError),
        (404, NotFoundError, ValueError),
        (409, KomootAPIError, None),
        (418, KomootAPIError, None),
        (429, RateLimitError, None),
        (500, ServerError, None),
        (502, ServerError, None),
        (503, ServerError, None),
        (504, ServerError, None),
    ],
)
def test_status_codes_map_to_exceptions(
    client: HttpClient,
    mocked_responses: responses.RequestsMock,
    status: int,
    exception: type[KomootAPIError],
    builtin: type[Exception] | None,
) -> None:
    mocked_responses.get(URL, status=status, body='<html>nope</html>')

    with pytest.raises(exception) as caught:
        client.request('GET', URL)

    assert type(caught.value) is exception
    assert caught.value.status_code == status
    assert caught.value.url == URL
    assert caught.value.body == '<html>nope</html>'
    if builtin is not None:
        assert isinstance(caught.value, builtin)


@pytest.mark.parametrize('status', [200, 201, 202, 204])
def test_2xx_statuses_are_successful(client: HttpClient, mocked_responses: responses.RequestsMock, status: int) -> None:
    mocked_responses.get(URL, status=status)

    assert client.request('GET', URL).status_code == status


def test_server_message_is_included_in_the_error(client: HttpClient, mocked_responses: responses.RequestsMock) -> None:
    body = {'error': 'BadCredentials', 'code': 401, 'message': 'Unknown user or wrong credentials.'}
    mocked_responses.get(URL, status=401, json=body)

    with pytest.raises(AuthenticationError, match='Unknown user or wrong credentials'):
        client.request('GET', URL)


@pytest.mark.parametrize('body', ['[1, 2]', '{"message": 3}', '{"message": ""}', 'not json'])
def test_unusable_error_bodies_are_ignored(
    client: HttpClient, mocked_responses: responses.RequestsMock, body: str
) -> None:
    mocked_responses.get(URL, status=404, body=body)

    with pytest.raises(NotFoundError) as caught:
        client.request('GET', URL)

    assert caught.value.message == 'The requested resource was not found'


def test_rate_limit_error_carries_retry_after(client: HttpClient, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, status=429, headers={'Retry-After': '12'})

    with pytest.raises(RateLimitError) as caught:
        client.request('GET', URL)

    assert caught.value.retry_after == 12.0


@pytest.mark.parametrize(
    ('value', 'expected'),
    [(None, None), ('5', 5.0), ('1.5', 1.5), ('-3', 0.0), ('soon', None), ('Mon, 99 Foo 2020 00:00:00 GMT', None)],
)
def test_parse_retry_after(value: str | None, expected: float | None) -> None:
    assert parse_retry_after(value) == expected


def test_parse_retry_after_http_date() -> None:
    in_a_minute = format_datetime(datetime.now(UTC) + timedelta(seconds=60), usegmt=True)
    long_ago = format_datetime(datetime(2000, 1, 1, tzinfo=UTC), usegmt=True)

    assert 50 < (parse_retry_after(in_a_minute) or 0) <= 60
    assert parse_retry_after(long_ago) == 0.0


# ----------------------------------------------------------------- transport errors


def test_timeout_is_wrapped(client: HttpClient, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, body=requests.ReadTimeout('too slow'))

    with pytest.raises(KomootTimeoutError) as caught:
        client.request('GET', URL)

    assert isinstance(caught.value, KomootConnectionError)
    assert isinstance(caught.value, ConnectionError)
    assert isinstance(caught.value.__cause__, requests.ReadTimeout)


def test_connection_error_is_wrapped(client: HttpClient, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, body=requests.ConnectionError('DNS failure'))

    with pytest.raises(KomootConnectionError, match='DNS failure') as caught:
        client.request('GET', URL)

    assert not isinstance(caught.value, KomootTimeoutError)
    assert isinstance(caught.value.__cause__, requests.ConnectionError)


def test_other_request_errors_are_wrapped_without_secrets(
    client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(URL, body=requests.exceptions.ChunkedEncodingError(f'broken body of {URL}?share_token=S3CRET'))

    with pytest.raises(KomootConnectionError, match='broken body') as caught:
        client.request('GET', URL, params={'share_token': 'S3CRET'})

    assert 'S3CRET' not in str(caught.value)


# ----------------------------------------------------------------- request details


def test_default_headers_timeout_and_auth(client: HttpClient, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL)
    client.auth = ('user', 'token')

    client.request('GET', URL, params={'a': 1, 'skipped': None})

    call = mocked_responses.calls[0]
    assert call.request.headers['User-Agent'] == USER_AGENT == f'kompy/{__version__} (+https://github.com/Tsadoq/kompy)'
    assert call.request.headers['Authorization'] == 'Basic dXNlcjp0b2tlbg=='  # base64('user:token')
    assert call.request.url == f'{URL}?a=1'
    assert sent_timeout(call.request) == DEFAULT_TIMEOUT == (5.0, 30.0)


def test_per_request_auth_overrides_default(client: HttpClient, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL)
    client.auth = ('user', 'token')

    client.request('GET', URL, auth=('a', 'b'))

    assert mocked_responses.calls[0].request.headers['Authorization'] == 'Basic YTpi'  # base64('a:b')


def test_custom_timeout(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL)

    HttpClient(timeout=2.5).request('GET', URL)

    assert sent_timeout(mocked_responses.calls[0].request) == 2.5


def test_negative_max_retries_is_rejected() -> None:
    with pytest.raises(ValueError, match='max_retries'):
        HttpClient(max_retries=-1)


# ----------------------------------------------------------------- retries


def test_retry_policy() -> None:
    adapter = HttpClient(max_retries=2).session.get_adapter('https://api.komoot.de')
    retry = adapter.max_retries  # type: ignore[attr-defined]

    assert retry.total == 2
    assert set(retry.status_forcelist) == {429, 502, 503, 504}
    assert retry.respect_retry_after_header is True
    assert retry.backoff_factor == 0.5
    assert retry.raise_on_status is False
    assert retry.allowed_methods == {'GET', 'HEAD', 'OPTIONS'}


def test_retries_can_be_disabled(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, status=429)

    with pytest.raises(RateLimitError):
        HttpClient(max_retries=0).request('GET', URL)

    assert len(mocked_responses.calls) == 1


def test_get_is_retried_after_429(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, status=429, headers={'Retry-After': '7'})
    mocked_responses.get(URL, json={'ok': True})

    response = HttpClient(max_retries=3).request('GET', URL)

    assert response.json() == {'ok': True}
    assert len(mocked_responses.calls) == 2


@pytest.mark.parametrize('status', [502, 503, 504])
def test_get_is_retried_after_gateway_errors(mocked_responses: responses.RequestsMock, status: int) -> None:
    mocked_responses.get(URL, status=status)
    mocked_responses.get(URL, status=200)

    assert HttpClient(max_retries=1).request('GET', URL).status_code == 200
    assert len(mocked_responses.calls) == 2


def test_exhausted_retries_raise_the_mapped_error(mocked_responses: responses.RequestsMock) -> None:
    for _ in range(4):
        mocked_responses.get(URL, status=503)

    with pytest.raises(ServerError):
        HttpClient(max_retries=3).request('GET', URL)

    assert len(mocked_responses.calls) == 4


def test_500_is_not_retried(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, status=500)

    with pytest.raises(ServerError):
        HttpClient(max_retries=3).request('GET', URL)

    assert len(mocked_responses.calls) == 1


@pytest.mark.parametrize('method', ['POST', 'PATCH', 'PUT', 'DELETE'])
def test_non_idempotent_requests_are_not_retried(mocked_responses: responses.RequestsMock, method: str) -> None:
    mocked_responses.add(method, URL, status=503)

    with pytest.raises(ServerError):
        HttpClient(max_retries=3).request(method, URL)

    assert len(mocked_responses.calls) == 1


# ----------------------------------------------------------------- JSON and lifecycle


def test_request_json_sends_accept_header(client: HttpClient, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, json={'a': 1})

    assert client.request_json('GET', URL) == {'a': 1}
    assert mocked_responses.calls[0].request.headers['Accept'] == 'application/hal+json, application/json'


@pytest.mark.parametrize(('body', 'match'), [('not json', 'not JSON'), ('[1, 2]', 'expected an object')])
def test_decode_json_object_rejects_unexpected_bodies(
    client: HttpClient, mocked_responses: responses.RequestsMock, body: str, match: str
) -> None:
    mocked_responses.get(URL, body=body)

    with pytest.raises(KomootResponseError, match=match):
        decode_json_object(client.request('GET', URL))


def test_close_closes_own_session(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HttpClient()
    closed: list[bool] = []
    monkeypatch.setattr(client.session, 'close', lambda: closed.append(True))

    client.close()

    assert closed == [True]


def test_close_leaves_a_provided_session_open(mocked_responses: responses.RequestsMock) -> None:
    session = requests.Session()
    session.headers['X-Custom'] = 'yes'
    closed: list[bool] = []
    session.close = lambda: closed.append(True)  # type: ignore[method-assign]
    client = HttpClient(session=session)
    mocked_responses.get(URL)

    client.request('GET', URL)
    client.close()

    assert closed == []
    assert client.session is session
    headers = mocked_responses.calls[0].request.headers
    assert headers['X-Custom'] == 'yes'
    assert headers['User-Agent'] == USER_AGENT


def test_delete_is_not_retried_so_a_succeeded_delete_is_not_reported_missing(
    mocked_responses: responses.RequestsMock,
) -> None:
    # A gateway error after the backend deleted the tour; a retry would get 404 and report NotFoundError.
    mocked_responses.delete(URL, status=504)

    with pytest.raises(ServerError):
        HttpClient(max_retries=3).request('DELETE', URL)

    assert len(mocked_responses.calls) == 1


# ----------------------------------------------------------------- Retry-After handling


@pytest.mark.parametrize(
    ('header', 'expected'),
    [('7', 7.0), ('1.5', 1.5), ('soon', 0.0), ('', 0.0), ('-3', 0.0), ('3600', MAX_RETRY_AFTER)],
)
def test_retry_policy_parses_retry_after_leniently_and_caps_it(header: str, expected: float) -> None:
    assert _KompyRetry(total=1).parse_retry_after(header) == expected


def test_too_long_retry_after_is_not_waited_for(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, status=429, headers={'Retry-After': '3600'})

    with pytest.raises(RateLimitError) as caught:
        HttpClient(max_retries=3).request('GET', URL)

    assert caught.value.retry_after == 3600.0
    assert len(mocked_responses.calls) == 1  # handed back at once instead of sleeping for hours


def test_retry_after_within_the_cap_is_retried(mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(URL, status=429, headers={'Retry-After': str(int(MAX_RETRY_AFTER))})
    mocked_responses.get(URL, json={'ok': True})

    assert HttpClient(max_retries=1).request('GET', URL).json() == {'ok': True}


# ----------------------------------------------------------------- redaction of secrets and personal data


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('https://x/v007/tours/1?share_token=SECRET', 'https://x/v007/tours/1?share_token=***'),
        ('https://x/1.gpx?a=1&share_token=SECRET&b=2', 'https://x/1.gpx?a=1&share_token=***&b=2'),
        ('https://x/v006/account/email/jane%40x.com/', 'https://x/v006/account/email/***/'),
        ('url: /v006/account/email/jane@x.com/ (Caused by ...)', 'url: /v006/account/email/***/ (Caused by ...)'),
        ('https://x/v007/tours/1?limit=5', 'https://x/v007/tours/1?limit=5'),
    ],
)
def test_redact(text: str, expected: str) -> None:
    assert redact(text) == expected


def test_share_token_is_absent_from_errors_and_logs(
    client: HttpClient, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture
) -> None:
    mocked_responses.get(URL, status=404)
    caplog.set_level('DEBUG', logger='kompy')

    with pytest.raises(NotFoundError) as caught:
        client.request('GET', URL, params={'share_token': 'SECRET_SHARE_TOKEN'})

    assert 'SECRET_SHARE_TOKEN' not in str(caught.value)
    assert 'SECRET_SHARE_TOKEN' not in caught.value.url
    assert 'share_token=***' in caught.value.url
    assert caplog.records  # the request was logged ...
    assert 'SECRET_SHARE_TOKEN' not in caplog.text  # ... without the token


def test_login_email_is_absent_from_errors_and_debug_logs(
    client: HttpClient, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture
) -> None:
    url = build_url('https://api.komoot.de/v006/account/email/{email}/', email='jane.doe@example.com')
    mocked_responses.get(url, body=requests.ConnectionError(f'Max retries exceeded with url: {url}'))
    caplog.set_level('DEBUG', logger='kompy')

    with pytest.raises(KomootConnectionError) as caught:
        client.request('GET', url)

    assert 'jane.doe' not in str(caught.value)
    assert 'jane.doe' not in caplog.text


def test_json_errors_do_not_reveal_the_share_token(
    client: HttpClient, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(URL, body='not json')

    with pytest.raises(KomootResponseError) as caught:
        decode_json_object(client.request('GET', URL, params={'share_token': 'SECRET'}))

    assert 'SECRET' not in str(caught.value)
