"""
Tests of :class:`kompy._http.HttpClient` through the real ``requests``/urllib3 transport.

``responses`` replaces the transport, so it cannot show how urllib3 reports a read timeout behind the retry adapter,
or how it parses ``Retry-After`` while sleeping. These tests run a tiny HTTP server on ``127.0.0.1`` instead.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from kompy._http import HttpClient
from kompy.exceptions import KomootConnectionError, KomootTimeoutError, NotFoundError, RateLimitError, ServerError
from tests.conftest import LOCALHOST

Responder = Callable[[BaseHTTPRequestHandler, int], None]
"""Answers a request, given the handler and how many requests the server got for this path before (0, 1, ...)."""


class _Server:
    """A local HTTP server whose answer per path is set by the test."""

    def __init__(self) -> None:
        self.routes: dict[str, Responder] = {}
        self.hits: dict[str, int] = {}
        server = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self) -> None:
                count = server.hits.get(self.path, 0)
                server.hits[self.path] = count + 1
                server.routes[self.path](self, count)

            do_GET = do_DELETE = _answer  # names required by BaseHTTPRequestHandler

            def log_message(self, *_args: object) -> None:  # keep the test output clean
                return

        self.httpd = ThreadingHTTPServer((LOCALHOST, 0), Handler)
        self.httpd.daemon_threads = True
        self.base = f'http://{LOCALHOST}:{self.httpd.server_address[1]}'

    def url(self, path: str) -> str:
        return f'{self.base}{path}'


def _reply(status: int, headers: dict[str, str] | None = None, body: bytes = b'{}') -> Responder:
    """A responder that always sends the same response."""

    def respond(handler: BaseHTTPRequestHandler, _count: int) -> None:
        handler.send_response(status)
        for name, value in (headers or {}).items():
            handler.send_header(name, value)
        handler.send_header('Content-Type', 'application/json')
        handler.send_header('Content-Length', str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    return respond


def _sequence(*responders: Responder) -> Responder:
    """A responder that answers the n-th request with the n-th responder (the last one repeats)."""

    def respond(handler: BaseHTTPRequestHandler, count: int) -> None:
        responders[min(count, len(responders) - 1)](handler, count)

    return respond


@pytest.fixture
def server() -> Iterator[_Server]:
    local = _Server()
    thread = threading.Thread(target=local.httpd.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    yield local
    local.httpd.shutdown()
    local.httpd.server_close()


@pytest.mark.parametrize('max_retries', [0, 1])
def test_read_timeout_behind_the_retry_adapter_is_a_timeout_error(server: _Server, max_retries: int) -> None:
    def slow(handler: BaseHTTPRequestHandler, count: int) -> None:
        time.sleep(0.5)
        _reply(200)(handler, count)

    server.routes['/slow'] = slow
    client = HttpClient(timeout=(2.0, 0.1), max_retries=max_retries)

    with pytest.raises(KomootTimeoutError, match='timed out') as caught:
        client.request('GET', server.url('/slow'))

    assert isinstance(caught.value, KomootConnectionError)  # still caught by the broader class
    assert 'Could not reach' not in str(caught.value)
    client.close()


def test_refused_connection_is_a_connection_error_not_a_timeout() -> None:
    with socket.socket() as probe:  # find a port nothing listens on
        probe.bind((LOCALHOST, 0))
        port = probe.getsockname()[1]
    # Windows retries refused SYNs for about two seconds before giving up, so leave headroom.
    client = HttpClient(timeout=(10.0, 2.0), max_retries=0)

    with pytest.raises(KomootConnectionError) as caught:
        client.request('GET', f'http://{LOCALHOST}:{port}/unreachable')

    assert not isinstance(caught.value, KomootTimeoutError)
    client.close()


@pytest.mark.parametrize('header', ['0.2', 'soon'])
def test_malformed_retry_after_falls_back_to_backoff(server: _Server, header: str) -> None:
    server.routes['/limited'] = _sequence(_reply(429, {'Retry-After': header}), _reply(200, body=b'{"ok": true}'))
    client = HttpClient(max_retries=1)

    assert client.request('GET', server.url('/limited')).json() == {'ok': True}
    assert server.hits['/limited'] == 2
    client.close()


def test_malformed_retry_after_without_retries_is_a_rate_limit_error(server: _Server) -> None:
    server.routes['/limited'] = _reply(429, {'Retry-After': 'soon'})
    client = HttpClient(max_retries=2)

    with pytest.raises(RateLimitError) as caught:
        client.request('GET', server.url('/limited'))

    assert caught.value.retry_after is None
    assert server.hits['/limited'] == 3
    client.close()


def test_huge_retry_after_is_raised_at_once(server: _Server) -> None:
    server.routes['/limited'] = _reply(429, {'Retry-After': '3600'})
    client = HttpClient(max_retries=3)
    started = time.monotonic()

    with pytest.raises(RateLimitError) as caught:
        client.request('GET', server.url('/limited'))

    assert time.monotonic() - started < 5
    assert caught.value.retry_after == 3600.0
    assert server.hits['/limited'] == 1
    client.close()


def test_delete_after_gateway_error_is_not_retried(server: _Server) -> None:
    server.routes['/tour'] = _sequence(_reply(502), _reply(404))
    client = HttpClient(max_retries=3)

    with pytest.raises(ServerError):
        client.request('DELETE', server.url('/tour'))

    assert server.hits['/tour'] == 1  # a retry would have turned the successful delete into a NotFoundError
    with pytest.raises(NotFoundError):
        client.request('DELETE', server.url('/tour'))
    client.close()
