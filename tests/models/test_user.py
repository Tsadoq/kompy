"""Tests for :class:`kompy.User`."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from kompy import KomootImage, User
from kompy.constants import PrivacyStatus


def test_from_full_profile(api_fixture: Callable[[str], Any]) -> None:
    payload = api_fixture('user')

    user = User.from_dict(payload)

    assert user.username == '1234567890'
    assert user.display_name == 'Sample display_name'
    assert user.status is PrivacyStatus.PRIVATE
    assert user.locale == 'en_US'
    assert user.metric is True
    assert user.created_at == datetime(2021, 10, 24, 7, 38, 44, tzinfo=UTC)
    assert user.is_premium is None  # not part of the full profile
    assert isinstance(user.avatar, KomootImage)
    assert user.avatar.templated is True
    assert user.raw == payload


def test_from_embedded_profile(api_fixture: Callable[[str], Any]) -> None:
    user = User.from_dict(api_fixture('user_profile_embedded'))

    assert user.username == '1234567890'
    assert user.display_name == 'Sample display_name'
    assert user.is_premium is False
    assert user.status == 'private'
    assert user.locale is None
    assert user.metric is None
    assert user.created_at is None


def test_minimal_payload() -> None:
    user = User.from_dict({'username': 'jan'})

    assert user == User(username='jan')
    assert user.avatar is None


def test_unknown_status_is_kept() -> None:
    assert User.from_dict({'username': 'jan', 'status': 'secret'}).status == 'secret'


def test_username_is_required() -> None:
    with pytest.raises(KeyError):
        User.from_dict({'display_name': 'Nobody'})


def test_url() -> None:
    assert User('jan').url == 'https://www.komoot.com/user/jan'


def test_raw_is_not_part_of_repr_or_equality() -> None:
    assert 'raw' not in repr(User('jan', raw={'a': 1}))
    assert User('jan', raw={'a': 1}) == User('jan')
