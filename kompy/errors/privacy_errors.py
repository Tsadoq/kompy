"""Errors raised when a request would break Komoot's visibility rules."""

from __future__ import annotations

from kompy.exceptions import KomootError

__all__ = ['PrivacyError']


class PrivacyError(KomootError, ValueError):
    """
    Non-public tours of another user were requested; Komoot only lists the public tours of other users.

    :param usr: The user whose tours were requested.
    """

    def __init__(self, usr: str) -> None:
        self.usr = usr
        self.message = f'Cannot fetch non public tours from user "{self.usr}"'
        super().__init__(self.message)

    def __reduce__(self) -> tuple[type[PrivacyError], tuple[str]]:
        return type(self), (self.usr,)  # pickle with the constructor argument, not with the message
