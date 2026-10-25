"""
Exceptions raised by kompy.

Every exception kompy raises on purpose derives from :class:`KomootError`, so callers can catch everything with a
single ``except KomootError``. Several classes also derive from a builtin exception (``ConnectionError`` or
``ValueError``) because older kompy versions raised those builtins; existing ``except`` clauses keep working.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    'AuthenticationError',
    'DownloadError',
    'KomootAPIError',
    'KomootConnectionError',
    'KomootError',
    'KomootResponseError',
    'KomootTimeoutError',
    'NotFoundError',
    'RateLimitError',
    'ServerError',
    'UnsupportedFormatError',
    'UploadStatusError',
]

#: Maximum number of characters of a response body kept on :class:`KomootAPIError`.
MAX_BODY_LENGTH = 500


class KomootError(Exception):
    """Base class for every error raised by kompy."""


class KomootConnectionError(KomootError, ConnectionError):
    """The Komoot API could not be reached (DNS failure, refused connection, dropped connection, ...)."""


class KomootTimeoutError(KomootConnectionError):
    """The Komoot API did not answer within the configured timeout."""


class KomootAPIError(KomootError):
    """
    The Komoot API answered with a non-2xx status code.

    :param message: Human readable description of the failure.
    :param status_code: HTTP status code of the response.
    :param url: URL of the request that failed.
    :param body: Response body; it is truncated to :data:`MAX_BODY_LENGTH` characters.
    """

    def __init__(self, message: str, *, status_code: int, url: str, body: str = '') -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: int = status_code
        self.url: str = url
        self.body: str = body[:MAX_BODY_LENGTH]

    def __str__(self) -> str:
        return f'{self.message} (HTTP {self.status_code} for {self.url})'

    def __reduce__(self) -> tuple[Any, ...]:
        # BaseException pickles as cls(*self.args), which lacks the keyword-only arguments; rebuild explicitly so the
        # error survives pickle, copy and multiprocessing (e.g. a ProcessPoolExecutor downloading tours).
        kwargs = {'status_code': self.status_code, 'url': self.url, 'body': self.body}
        return _rebuild, (type(self), self.message, kwargs), self.__dict__


class AuthenticationError(KomootAPIError, ConnectionError):
    """The credentials were rejected (HTTP 401 or 403)."""


class NotFoundError(KomootAPIError, ValueError):
    """The requested resource does not exist or is not visible to the caller (HTTP 404)."""


class RateLimitError(KomootAPIError):
    """
    Too many requests were sent (HTTP 429).

    :param retry_after: Seconds to wait before retrying, taken from the ``Retry-After`` header when present.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        url: str,
        body: str = '',
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, url=url, body=body)
        self.retry_after: float | None = retry_after


class ServerError(KomootAPIError, ConnectionError):
    """
    The Komoot API failed internally (HTTP 5xx).

    It is also a ``ConnectionError``, which older kompy versions raised on HTTP 500.
    """


class KomootResponseError(KomootError, ValueError):
    """The Komoot API answered successfully, but the body could not be understood."""


class UnsupportedFormatError(KomootError, ValueError):
    """The requested format is not available for this resource (for example FIT for a recorded tour)."""


class DownloadError(KomootError):
    """
    Some tours of a bulk download (``KomootConnector.download_tours``) could not be downloaded.

    The other tours were downloaded anyway; their files are listed in :attr:`paths`.

    :param message: Human readable description of the failure.
    :param paths: Files that were written, or that already existed and were kept.
    :param failures: The error raised for each tour that failed, keyed by tour id.
    """

    def __init__(self, message: str, *, paths: list[Path], failures: dict[int, KomootError]) -> None:
        super().__init__(message)
        self.message: str = message
        self.paths: list[Path] = paths
        self.failures: dict[int, KomootError] = failures

    def __reduce__(self) -> tuple[Any, ...]:
        return _rebuild, (type(self), self.message, {'paths': self.paths, 'failures': self.failures}), self.__dict__


class UploadStatusError(KomootError):
    """
    A tour was uploaded, but Komoot did not give it the requested visibility and changing it afterwards failed.

    The tour exists with the visibility in :attr:`actual_status`: change it with ``KomootConnector.change_tour``
    or delete it.

    :param message: Human readable description of the failure.
    :param tour_id: Id of the uploaded tour.
    :param requested_status: The visibility that was asked for.
    :param actual_status: The visibility the tour has, as reported by Komoot (``None`` if unknown).
    """

    def __init__(self, message: str, *, tour_id: int, requested_status: str, actual_status: str | None) -> None:
        super().__init__(message)
        self.message: str = message
        self.tour_id: int = tour_id
        self.requested_status: str = requested_status
        self.actual_status: str | None = actual_status

    def __reduce__(self) -> tuple[Any, ...]:
        kwargs = {
            'tour_id': self.tour_id,
            'requested_status': self.requested_status,
            'actual_status': self.actual_status,
        }
        return _rebuild, (type(self), self.message, kwargs), self.__dict__


def _rebuild(cls: type[Exception], message: str, kwargs: dict[str, Any]) -> Exception:
    """Recreate an exception that takes keyword-only arguments (used when unpickling)."""
    return cls(message, **kwargs)
