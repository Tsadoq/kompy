"""
Private HTTP layer of kompy.

:class:`HttpClient` wraps a single :class:`requests.Session` and is the only place that talks to the network. It
sets the timeout, the ``User-Agent`` and the credentials, retries idempotent requests on transient errors, and
turns every failure into an exception of :mod:`kompy.exceptions`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, Final, Self, TypeAlias, cast
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import MaxRetryError, NewConnectionError, ResponseError, TimeoutError as Urllib3TimeoutError
from urllib3.util.retry import Retry

from kompy import __version__
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

if TYPE_CHECKING:
    from types import TracebackType

    from urllib3.connectionpool import ConnectionPool
    from urllib3.response import BaseHTTPResponse

__all__ = [
    'DEFAULT_MAX_RETRIES',
    'DEFAULT_TIMEOUT',
    'MAX_RETRY_AFTER',
    'RETRY_METHODS',
    'USER_AGENT',
    'HttpClient',
    'Timeout',
    'build_url',
    'decode_json_object',
    'parse_retry_after',
    'raise_for_status',
    'redact',
]

logger = logging.getLogger(__name__)

Timeout: TypeAlias = float | tuple[float, float]
"""A timeout in seconds: one value for both phases, or a ``(connect, read)`` pair."""

DEFAULT_TIMEOUT: Final[tuple[float, float]] = (5.0, 30.0)
"""Default ``(connect, read)`` timeout in seconds."""

DEFAULT_MAX_RETRIES: Final[int] = 3
"""Default number of retries for idempotent requests that fail with a transient error."""

DEFAULT_BACKOFF_FACTOR: Final[float] = 0.5
"""Base of the exponential backoff between retries, in seconds (0.5s, 1s, 2s, ...)."""

RETRY_STATUSES: Final[frozenset[int]] = frozenset({429, 502, 503, 504})
"""Status codes worth retrying: rate limiting and temporary gateway/server unavailability."""

RETRY_METHODS: Final[frozenset[str]] = frozenset({'GET', 'HEAD', 'OPTIONS'})
"""Methods retried on a transient error. Uploads, edits and deletes are never retried: a retried DELETE whose first
attempt succeeded behind a failing gateway would report a misleading 404."""

MAX_RETRY_AFTER: Final[float] = 60.0
"""Longest ``Retry-After`` delay, in seconds, that kompy waits for before retrying by itself. When Komoot asks for a
longer pause, the request is not retried and the HTTP 429 is raised as :class:`RateLimitError` (with
``retry_after``), so the caller decides what to do instead of being blocked silently."""

USER_AGENT: Final[str] = f'kompy/{__version__} (+https://github.com/Tsadoq/kompy)'
"""``User-Agent`` header sent with every request (the upload endpoint requires one)."""


def build_url(template: str, **segments: object) -> str:
    """
    Fill the placeholders of a URL template, URL-quoting every value.

    Quoting keeps values such as an email address containing ``#`` or ``?``, or an identifier containing ``/``,
    inside their path segment. ``@`` is left as is, so email addresses stay readable.

    >>> build_url('https://api.komoot.de/v006/account/email/{email_address}/', email_address='a#b@example.com')
    'https://api.komoot.de/v006/account/email/a%23b@example.com/'

    :param template: A URL with ``{name}`` placeholders.
    :param segments: The value of each placeholder.
    :return: The URL.
    """
    return template.format(**{name: quote(str(value), safe='@') for name, value in segments.items()})


_SENSITIVE_PARAMS: Final[frozenset[str]] = frozenset({'share_token', 'token', 'password'})
_SENSITIVE_QUERY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r'(?P<key>(?:share_token|token|password)=)[^&#\s\'"]*', re.IGNORECASE
)
_EMAIL_SEGMENT_PATTERN: Final[re.Pattern[str]] = re.compile(r'(?P<key>/account/email/)[^/?#\s\'"]*')
_REDACTED: Final[str] = '***'


def redact(text: str) -> str:
    """
    Hide the secrets and personal data a URL (or a message containing URLs) may carry.

    Share tokens grant access to private tours and the login URL contains the email address of the account, so
    neither may end up in exception messages, tracebacks or logs, which users paste into bug reports.

    >>> redact('https://api.komoot.de/v007/tours/1.gpx?share_token=abc&x=1')
    'https://api.komoot.de/v007/tours/1.gpx?share_token=***&x=1'
    >>> redact('https://api.komoot.de/v006/account/email/jane@example.com/')
    'https://api.komoot.de/v006/account/email/***/'

    :param text: A URL or a message.
    :return: The text with the values of sensitive query parameters and the login email address replaced by
        ``***``.
    """
    text = _SENSITIVE_QUERY_PATTERN.sub(rf'\g<key>{_REDACTED}', text)
    return _EMAIL_SEGMENT_PATTERN.sub(rf'\g<key>{_REDACTED}', text)


def _redact_params(params: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Copy query parameters, hiding the values of the sensitive ones."""
    if params is None:
        return None
    return {key: _REDACTED if key.lower() in _SENSITIVE_PARAMS else value for key, value in params.items()}


def raise_for_status(response: requests.Response) -> None:
    """
    Raise the kompy exception matching a non-2xx response.

    :param response: The response to check.
    :raises AuthenticationError: On HTTP 401 or 403.
    :raises NotFoundError: On HTTP 404.
    :raises RateLimitError: On HTTP 429.
    :raises ServerError: On HTTP 5xx.
    :raises KomootAPIError: On any other non-2xx status.
    """
    status = response.status_code
    if 200 <= status < 300:
        return
    details: dict[str, Any] = {'status_code': status, 'url': redact(response.url), 'body': response.text}
    reason = _server_message(response)
    suffix = f': {reason}' if reason else ''
    if status == 401:
        raise AuthenticationError(f'Komoot rejected the credentials{suffix}', **details)
    if status == 403:
        raise AuthenticationError(f'Komoot denied access to this resource{suffix}', **details)
    if status == 404:
        raise NotFoundError(f'The requested resource was not found{suffix}', **details)
    if status == 429:
        retry_after = parse_retry_after(response.headers.get('Retry-After'))
        raise RateLimitError(f'Too many requests to the Komoot API{suffix}', retry_after=retry_after, **details)
    if status >= 500:
        raise ServerError(f'The Komoot API failed to process the request{suffix}', **details)
    raise KomootAPIError(f'The Komoot API rejected the request{suffix}', **details)


def parse_retry_after(value: str | None) -> float | None:
    """
    Parse a ``Retry-After`` header.

    :param value: The header value, either a number of seconds or an HTTP date.
    :return: The number of seconds to wait (never negative), or ``None`` when absent or unparseable.
    """
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        moment = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, (moment - datetime.now(UTC)).total_seconds())


def _server_message(response: requests.Response) -> str | None:
    """
    Extract the human readable error message from a Komoot error body such as
    ``{"error": "BadCredentials", "code": 401, "message": "Unknown user or wrong credentials."}``.
    """
    try:
        payload = response.json()
    except ValueError:
        return None
    message = payload.get('message') if isinstance(payload, Mapping) else None
    return message if isinstance(message, str) and message else None


class _KompyRetry(Retry):
    """
    The urllib3 retry policy of kompy.

    Compared to :class:`urllib3.util.retry.Retry` it parses ``Retry-After`` leniently (a malformed value such as
    ``'1.5'`` or ``'soon'`` falls back to the exponential backoff instead of failing the request with
    ``InvalidHeader``) and it never sleeps longer than :data:`MAX_RETRY_AFTER`: when the server asks for a longer
    pause, retrying stops and the response is handed back, to be raised as :class:`RateLimitError`.
    """

    def parse_retry_after(self, retry_after: str) -> float:
        """Parse a ``Retry-After`` value; ``0`` (use the backoff) when it cannot be understood."""
        seconds = parse_retry_after(retry_after)
        return 0.0 if seconds is None else min(seconds, MAX_RETRY_AFTER)

    def increment(
        self,
        method: str | None = None,
        url: str | None = None,
        response: BaseHTTPResponse | None = None,
        error: Exception | None = None,
        _pool: ConnectionPool | None = None,
        _stacktrace: TracebackType | None = None,
    ) -> Self:
        """Count a retry, refusing it when the server asks to wait longer than :data:`MAX_RETRY_AFTER`."""
        if response is not None:
            seconds = parse_retry_after(response.headers.get('Retry-After'))
            if seconds is not None and seconds > MAX_RETRY_AFTER:
                logger.debug('Not retrying %s %s: Retry-After of %.0fs is too long.', method, redact(str(url)), seconds)
                # The connection pool urlopen() catches this, and returns the response as raise_on_status is off.
                raise MaxRetryError(cast('ConnectionPool', _pool), str(url), ResponseError('Retry-After too long'))
        return super().increment(method, url, response, error, _pool, _stacktrace)


class HttpClient:
    """
    A ``requests`` session configured for the Komoot API.

    :param timeout: Timeout in seconds of every request, one value or a ``(connect, read)`` pair.
    :param max_retries: How many times a read-only request (GET, HEAD, OPTIONS) is retried after a connection
        error or an HTTP 429/502/503/504, with exponential backoff. A ``Retry-After`` header of up to
        :data:`MAX_RETRY_AFTER` seconds is respected; a longer one stops the retries and raises
        :class:`RateLimitError` right away. Uploads, edits and deletes are never retried. ``0`` disables retries.
    :param session: An existing session to use, e.g. one configured with proxies or custom certificates. kompy sets
        its ``User-Agent`` header and mounts its retry adapter on it, but does not close it: its owner does.
    :raises ValueError: If ``max_retries`` is negative.
    """

    def __init__(
        self,
        *,
        timeout: Timeout = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        session: requests.Session | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError(f'max_retries must be 0 or greater, got {max_retries}.')
        self.timeout: Timeout = timeout
        self.auth: tuple[str, str] | None = None
        """Basic auth credentials sent with every request that does not pass its own."""
        self._owns_session = session is None
        self.session: requests.Session = requests.Session() if session is None else session
        self.session.headers['User-Agent'] = USER_AGENT
        retry = _KompyRetry(
            total=max_retries,
            backoff_factor=DEFAULT_BACKOFF_FACTOR,
            status_forcelist=RETRY_STATUSES,
            allowed_methods=RETRY_METHODS,
            respect_retry_after_header=True,
            raise_on_status=False,  # hand the last response back so it is mapped to a kompy exception
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        json: Any = None,
        data: bytes | None = None,
        auth: tuple[str, str] | None = None,
    ) -> requests.Response:
        """
        Send a request and return the response if its status is 2xx.

        :param method: HTTP method, e.g. ``'GET'``.
        :param url: Full URL (see :func:`build_url`).
        :param params: Query string parameters; ``None`` values are left out.
        :param headers: Extra headers.
        :param json: JSON body.
        :param data: Raw body.
        :param auth: Basic auth credentials for this request only; defaults to :attr:`auth`.
        :return: The successful response.
        :raises KomootTimeoutError: If the request timed out.
        :raises KomootConnectionError: If the API could not be reached.
        :raises KomootAPIError: If the API answered with a non-2xx status (see :func:`raise_for_status`).
        """
        safe_url = redact(url)
        logger.debug('%s %s params=%s', method, safe_url, _redact_params(params))
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                headers=headers,
                json=json,
                data=data,
                auth=auth or self.auth,
                timeout=self.timeout,
            )
        except requests.Timeout as error:
            raise KomootTimeoutError(f'{method} {safe_url} timed out.') from error
        except requests.ConnectionError as error:
            # With retries enabled, urllib3 wraps a read timeout in MaxRetryError, which requests reports as a
            # plain ConnectionError: unwrap it so that every timeout is a KomootTimeoutError.
            if _is_timeout(error):
                raise KomootTimeoutError(f'{method} {safe_url} timed out.') from error
            raise KomootConnectionError(
                f'Could not reach the Komoot API ({method} {safe_url}): {redact(str(error))}'
            ) from error
        except requests.RequestException as error:
            raise KomootConnectionError(
                f'Could not reach the Komoot API ({method} {safe_url}): {redact(str(error))}'
            ) from error
        logger.debug('%s %s -> HTTP %s', method, safe_url, response.status_code)
        raise_for_status(response)
        return response

    def request_json(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        auth: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Send a request and decode its JSON object body.

        :param method: HTTP method, e.g. ``'GET'``.
        :param url: Full URL.
        :param params: Query string parameters.
        :param auth: Basic auth credentials for this request only.
        :return: The decoded body.
        :raises KomootResponseError: If the body is not a JSON object.
        :raises KomootError: For the failures listed in :meth:`request`.
        """
        response = self.request(
            method, url, params=params, headers={'Accept': 'application/hal+json, application/json'}, auth=auth
        )
        return decode_json_object(response)

    def close(self) -> None:
        """Close the session, unless it was passed in by the caller (who then owns it)."""
        if self._owns_session:
            self.session.close()


def _is_timeout(error: requests.ConnectionError) -> bool:
    """Tell whether the urllib3 error behind a ``requests`` connection error (the reason of a ``MaxRetryError``)
    is a timeout. ``NewConnectionError`` (e.g. a refused connection) derives from urllib3's timeout errors for
    historical reasons, but is not one."""
    cause = error.args[0] if error.args else None
    reason = getattr(cause, 'reason', cause)
    return isinstance(reason, Urllib3TimeoutError) and not isinstance(reason, NewConnectionError)


def decode_json_object(response: requests.Response) -> dict[str, Any]:
    """
    Decode a response body that must be a JSON object.

    :param response: The response.
    :return: The decoded object.
    :raises KomootResponseError: If the body is not valid JSON or not an object.
    """
    try:
        payload = response.json()
    except ValueError as error:
        raise KomootResponseError(
            f'The Komoot API returned a body that is not JSON ({redact(response.url)}).'
        ) from error
    if not isinstance(payload, dict):
        raise KomootResponseError(
            f'The Komoot API returned unexpected JSON ({redact(response.url)}): expected an object.'
        )
    return payload
