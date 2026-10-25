"""Tests for the errors kept at their historical paths and for :class:`kompy.exceptions.DownloadError`."""

from __future__ import annotations

from pathlib import Path

import pytest

import kompy
from kompy.errors import NotEmailError as ReExportedNotEmailError
from kompy.errors.initialisation_errors import NotEmailError
from kompy.errors.privacy_errors import PrivacyError
from kompy.exceptions import DownloadError, KomootError, NotFoundError


def test_not_email_error() -> None:
    error = NotEmailError('nope')

    assert isinstance(error, KomootError)
    assert isinstance(error, ValueError)
    assert error.email == 'nope'
    assert str(error) == error.message == '"nope" is not a valid email address.'


def test_privacy_error() -> None:
    error = PrivacyError('someone')

    assert isinstance(error, KomootError)
    assert isinstance(error, ValueError)
    assert error.usr == 'someone'
    assert str(error) == 'Cannot fetch non public tours from user "someone"'


def test_errors_are_reexported() -> None:
    assert ReExportedNotEmailError is NotEmailError is kompy.NotEmailError
    assert kompy.PrivacyError is PrivacyError
    assert kompy.DownloadError is DownloadError


def test_download_error() -> None:
    failure = NotFoundError('gone', status_code=404, url='u')

    error = DownloadError('1 failed', paths=[Path('a.gpx')], failures={7: failure})

    assert isinstance(error, KomootError)
    assert error.paths == [Path('a.gpx')]
    assert error.failures == {7: failure}
    assert str(error) == '1 failed'
    with pytest.raises(KomootError):
        raise error
