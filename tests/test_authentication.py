"""Tests for :class:`kompy.Authentication`."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from kompy import Authentication

EMAIL = 'test.person@example.com'
PASSWORD = 'password123-very-secret'
TOKEN = 'token-abcdef-0123456789'
USERNAME = '1234567890'


@pytest.fixture
def auth() -> Authentication:
    return Authentication(EMAIL, PASSWORD)


def test_getters(auth: Authentication) -> None:
    assert auth.get_email_address() == EMAIL
    assert auth.get_password() == PASSWORD
    assert not auth.is_logged_in()


def test_token_and_username_are_unset_before_login(auth: Authentication) -> None:
    with pytest.raises(ValueError, match='login first'):
        auth.get_token()
    with pytest.raises(ValueError, match='login first'):
        auth.get_username()


def test_setters(auth: Authentication) -> None:
    auth.set_token(TOKEN)
    auth.set_username(USERNAME)

    assert auth.get_token() == TOKEN
    assert auth.get_username() == USERNAME
    assert auth.is_logged_in()


def test_keyword_constructor() -> None:
    auth = Authentication(email_address=EMAIL, password=PASSWORD)

    assert auth.get_email_address() == EMAIL


@pytest.mark.parametrize(
    ('email', 'password', 'match'),
    [
        ('', PASSWORD, 'Email'),
        (EMAIL, '', 'Password'),
        ('', '', 'Email'),
        (None, None, 'Email'),
        (EMAIL, None, 'Password'),
    ],
)
def test_empty_credentials_are_rejected(email: str | None, password: str | None, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Authentication(email, password)


def test_long_values_are_kept() -> None:
    auth = Authentication('a' * 100 + '@example.com', 'p' * 100)

    assert auth.get_email_address() == 'a' * 100 + '@example.com'
    assert auth.get_password() == 'p' * 100


def test_token_mode() -> None:
    auth = Authentication(username=USERNAME, token=TOKEN)

    assert auth.get_username() == USERNAME
    assert auth.get_token() == TOKEN
    assert auth.is_logged_in()
    with pytest.raises(ValueError, match='only holds a username and token'):
        auth.get_email_address()
    with pytest.raises(ValueError, match='only holds a username and token'):
        auth.get_password()


def test_all_four_values() -> None:
    auth = Authentication(EMAIL, PASSWORD, username=USERNAME, token=TOKEN)

    assert auth.get_password() == PASSWORD
    assert auth.get_token() == TOKEN


@pytest.mark.parametrize(
    ('kwargs', 'match'),
    [
        ({'username': USERNAME}, 'Token'),
        ({'token': TOKEN}, 'Username'),
        ({'username': '', 'token': TOKEN}, 'Username'),
        ({'username': USERNAME, 'token': ''}, 'Token'),
        ({'email_address': EMAIL, 'username': USERNAME, 'token': TOKEN}, 'Password'),
    ],
)
def test_incomplete_token_mode_is_rejected(kwargs: dict[str, str], match: str) -> None:
    with pytest.raises(ValueError, match=match):
        Authentication(**kwargs)


@pytest.mark.parametrize('render', [str, repr])
def test_str_and_repr_before_login_do_not_crash_or_leak(auth: Authentication, render: Callable[[object], str]) -> None:
    text = render(auth)

    assert PASSWORD not in text
    assert '*' * len(PASSWORD) not in text  # not even the length of the password
    assert EMAIL not in text
    assert 'token=<unset>' in text
    assert 'username=None' in text


@pytest.mark.parametrize('render', [str, repr])
def test_str_and_repr_after_login_do_not_leak(auth: Authentication, render: Callable[[object], str]) -> None:
    auth.set_token(TOKEN)
    auth.set_username(USERNAME)

    text = render(auth)

    assert PASSWORD not in text
    assert TOKEN not in text
    assert EMAIL not in text
    assert USERNAME not in text
    assert text == "Authentication(email_address='te***om', username='12***90', token=<set>)"


def test_repr_masks_short_values_entirely() -> None:
    auth = Authentication('a@b.c', 'p', username='u1', token='t')

    assert repr(auth) == "Authentication(email_address='***', username='***', token=<set>)"


def test_repr_in_token_mode() -> None:
    assert repr(Authentication(username=USERNAME, token=TOKEN)) == (
        "Authentication(email_address=None, username='12***90', token=<set>)"
    )
