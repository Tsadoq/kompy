"""Credentials used to talk to the Komoot API."""

from __future__ import annotations

__all__ = ['Authentication']


class Authentication:
    """
    Credentials of a Komoot account.

    Komoot uses two kinds of credentials:

    * the email address and password, used once to log in;
    * the username and the API token returned by that login, used for every other request.

    An ``Authentication`` holds either the email address and password (the token and username are then filled in
    by the login), or only a username and token (see ``KomootConnector.from_token``). The token is
    password-equivalent: keep it as secret as the password. Neither ``str()`` nor ``repr()`` ever reveals the
    password or the token.

    :param email_address: The email address of the account.
    :param password: The password of the account.
    :param username: The username returned by a previous login (token mode).
    :param token: The API token returned by a previous login (token mode).
    :raises ValueError: If neither a complete email/password pair nor a complete username/token pair is given, or
        if a given value is empty.
    """

    def __init__(
        self,
        email_address: str | None = None,
        password: str | None = None,
        *,
        username: str | None = None,
        token: str | None = None,
    ) -> None:
        token_mode = username is not None or token is not None
        if not token_mode or email_address is not None or password is not None:
            if not email_address:
                raise ValueError('Email address cannot be empty.')
            if not password:
                raise ValueError('Password cannot be empty.')
        if token_mode:
            if not username:
                raise ValueError('Username cannot be empty.')
            if not token:
                raise ValueError('Token cannot be empty.')
        self._email_address: str | None = email_address
        self._password: str | None = password
        self._token: str | None = token
        self._username: str | None = username

    def get_email_address(self) -> str:
        """
        Get the email address.

        :return: The email address.
        :raises ValueError: If this authentication only holds a username and token.
        """
        if self._email_address is None:
            raise ValueError('No email address set: this authentication only holds a username and token.')
        return self._email_address

    def get_password(self) -> str:
        """
        Get the password.

        :return: The password.
        :raises ValueError: If this authentication only holds a username and token.
        """
        if self._password is None:
            raise ValueError('No password set: this authentication only holds a username and token.')
        return self._password

    def get_token(self) -> str:
        """
        Get the API token.

        :return: The token.
        :raises ValueError: If no token is set yet (log in first).
        """
        if self._token is None:
            raise ValueError('No token set, please login first.')
        return self._token

    def get_username(self) -> str:
        """
        Get the username.

        :return: The username.
        :raises ValueError: If no username is set yet (log in first).
        """
        if self._username is None:
            raise ValueError('No username set, please login first.')
        return self._username

    def set_token(self, token: str) -> None:
        """
        Set the API token.

        :param token: The token returned by the login.
        """
        self._token = token

    def set_username(self, username: str) -> None:
        """
        Set the username.

        :param username: The username returned by the login.
        """
        self._username = username

    def is_logged_in(self) -> bool:
        """
        Tell whether the username and token are known, i.e. whether API requests can be authenticated.

        :return: ``True`` once both the username and the token are set.
        """
        return self._username is not None and self._token is not None

    def __repr__(self) -> str:
        """
        Describe the credentials without revealing them: the email address and username are partially masked, the
        password and token are never shown (not even their length).
        """
        email = None if self._email_address is None else _mask(self._email_address)
        username = None if self._username is None else _mask(self._username)
        token = 'set' if self._token is not None else 'unset'
        return f'Authentication(email_address={email!r}, username={username!r}, token=<{token}>)'

    __str__ = __repr__


def _mask(value: str) -> str:
    """Keep only the first and last two characters of a value (nothing of very short values)."""
    if len(value) <= 6:
        return '***'
    return f'{value[:2]}***{value[-2:]}'
