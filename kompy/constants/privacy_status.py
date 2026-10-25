"""Visibility of Komoot resources."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['PrivacyStatus']


class PrivacyStatus(KomootStrEnum):
    """Privacy status (visibility) of a tour or a user profile."""

    PUBLIC = 'public'
    PRIVATE = 'private'
    FRIENDS = 'friends'
