"""Tests for the exception hierarchy in :mod:`kompy.exceptions`."""

from __future__ import annotations

import copy
import pickle
from pathlib import Path

import pytest

from kompy.errors.initialisation_errors import NotEmailError
from kompy.errors.privacy_errors import PrivacyError
from kompy.exceptions import (
    MAX_BODY_LENGTH,
    AuthenticationError,
    DownloadError,
    KomootAPIError,
    KomootConnectionError,
    KomootError,
    KomootResponseError,
    KomootTimeoutError,
    NotFoundError,
    RateLimitError,
    ServerError,
    UnsupportedFormatError,
    UploadStatusError,
)


@pytest.mark.parametrize(
    ('exception', 'bases'),
    [
        (KomootConnectionError, (KomootError, ConnectionError)),
        (KomootTimeoutError, (KomootConnectionError,)),
        (KomootAPIError, (KomootError,)),
        (AuthenticationError, (KomootAPIError, ConnectionError)),
        (NotFoundError, (KomootAPIError, ValueError)),
        (RateLimitError, (KomootAPIError,)),
        (ServerError, (KomootAPIError, ConnectionError)),  # kompy < 0.1 raised ConnectionError on HTTP 500
        (KomootResponseError, (KomootError, ValueError)),
        (UnsupportedFormatError, (KomootError, ValueError)),
    ],
)
def test_hierarchy_keeps_builtin_bases_for_backward_compatibility(
    exception: type[Exception], bases: tuple[type[Exception], ...]
) -> None:
    assert issubclass(exception, bases)


def test_api_error_attributes_and_message() -> None:
    error = KomootAPIError('Boom.', status_code=418, url='https://api.example.com/x', body='b' * 1000)

    assert error.message == 'Boom.'
    assert error.status_code == 418
    assert error.url == 'https://api.example.com/x'
    assert len(error.body) == MAX_BODY_LENGTH
    assert str(error) == 'Boom. (HTTP 418 for https://api.example.com/x)'


def test_rate_limit_error_retry_after() -> None:
    error = RateLimitError('Slow down.', status_code=429, url='u', retry_after=3.5)

    assert error.retry_after == 3.5
    assert RateLimitError('Slow down.', status_code=429, url='u').retry_after is None


def test_server_error_is_caught_by_old_connection_error_handlers() -> None:
    with pytest.raises(ConnectionError):
        raise ServerError('Internal error.', status_code=500, url='u')


@pytest.mark.parametrize(
    'error',
    [
        KomootAPIError('Boom.', status_code=418, url='u', body='body'),
        AuthenticationError('No.', status_code=401, url='u'),
        NotFoundError('Gone.', status_code=404, url='u'),
        RateLimitError('Slow down.', status_code=429, url='u', retry_after=3.5),
        ServerError('Oops.', status_code=503, url='u'),
        DownloadError(
            '1 tour(s) could not be downloaded: 7.',
            paths=[Path('a.gpx')],
            failures={7: NotFoundError('Gone.', status_code=404, url='u')},
        ),
        KomootTimeoutError('GET u timed out.'),
        KomootResponseError('Bad body.'),
        UnsupportedFormatError('No FIT.'),
        UploadStatusError('Tour 1 was uploaded ...', tour_id=1, requested_status='private', actual_status='friends'),
        NotEmailError('not-an-email'),
        PrivacyError('someone'),
    ],
    ids=lambda error: type(error).__name__,
)
def test_exceptions_survive_pickle_and_copy(error: KomootError) -> None:
    for clone in (pickle.loads(pickle.dumps(error)), copy.copy(error), copy.deepcopy(error)):
        assert type(clone) is type(error)
        assert str(clone) == str(error)
        assert vars(clone).keys() == vars(error).keys()
        for name, value in vars(error).items():
            if name == 'failures':
                assert {key: str(item) for key, item in getattr(clone, name).items()} == {
                    key: str(item) for key, item in value.items()
                }
            else:
                assert getattr(clone, name) == value
