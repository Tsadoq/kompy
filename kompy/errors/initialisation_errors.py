"""Errors raised while creating a :class:`kompy.KomootConnector`."""

from __future__ import annotations

from kompy.exceptions import KomootError

__all__ = ['NotEmailError']


class NotEmailError(KomootError, ValueError):
    """
    The email address given to log in is not a valid email address.

    :param email: The rejected value.
    """

    def __init__(self, email: str) -> None:
        self.email = email
        self.message = f'"{self.email}" is not a valid email address.'
        super().__init__(self.message)

    def __reduce__(self) -> tuple[type[NotEmailError], tuple[str]]:
        return type(self), (self.email,)  # pickle with the constructor argument, not with the message
