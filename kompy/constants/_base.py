"""Shared base class for kompy's string enumerations."""

from __future__ import annotations

from enum import StrEnum

__all__ = ['KomootStrEnum']


class KomootStrEnum(StrEnum):
    """
    String enumeration of values used by the Komoot API.

    Members are real ``str`` instances, so they compare equal to the plain strings the API uses
    (``SupportedActivities.HIKING == 'hike'``) and can be passed anywhere a string is expected.
    """

    @classmethod
    def list_all(cls) -> list[str]:
        """
        List the values of all members, in declaration order.

        :return: The plain string value of every member.
        """
        return [member.value for member in cls]
