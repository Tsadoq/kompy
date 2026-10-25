"""Komoot users."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Self

from kompy._parsing import (
    coerce_optional_enum,
    optional_bool,
    optional_str,
    parse_datetime,
    parse_optional,
    require_str,
)
from kompy.constants.privacy_status import PrivacyStatus
from kompy.image import KomootImage

__all__ = ['User']


@dataclass
class User:
    """
    A Komoot user.

    The API returns users in two shapes: the full profile of the logged-in user (``/users/{username}/``) and the
    short public profile embedded in other resources (``profile_embedded``, e.g. a tour's creator). Fields missing
    from the shape at hand are ``None``.

    :param username: The user's unique identifier (numeric for most accounts, despite the name).
    :param display_name: The name shown in the Komoot apps.
    :param avatar: The user's profile picture (templated).
    :param status: Visibility of the profile, usually a :class:`kompy.constants.PrivacyStatus`.
    :param is_premium: Whether the user has Komoot Premium (only in the short profile).
    :param locale: Preferred locale, e.g. ``'en_US'`` (only in the full profile).
    :param metric: Whether the user prefers metric units (only in the full profile).
    :param created_at: When the account was created (only in the full profile).
    :param raw: The payload the user was parsed from.
    """

    username: str
    display_name: str | None = None
    avatar: KomootImage | None = None
    status: PrivacyStatus | str | None = None
    is_premium: bool | None = None
    locale: str | None = None
    metric: bool | None = None
    created_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build a user from either the full profile or the ``profile_embedded`` payload.

        :param data: The user payload.
        :return: The parsed user.
        :raises KeyError: If ``username`` is missing.
        """
        return cls(
            username=require_str(data, 'username'),
            display_name=optional_str(data.get('display_name')),
            avatar=parse_optional(data.get('avatar'), KomootImage.from_dict),
            status=coerce_optional_enum(PrivacyStatus, data.get('status')),
            is_premium=optional_bool(data.get('is_premium')),
            locale=optional_str(data.get('locale')),
            metric=optional_bool(data.get('metric')),
            created_at=parse_datetime(data.get('created_at')),
            raw=dict(data),
        )

    @property
    def url(self) -> str:
        """Link to the user's public profile on komoot.com."""
        return f'https://www.komoot.com/user/{self.username}'
