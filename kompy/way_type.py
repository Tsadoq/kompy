"""Share of a tour on a given way type."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kompy._parsing import coerce_enum, require_str
from kompy.constants.way_type import PossibleWayType
from kompy.surface import normalize_amount

__all__ = ['WayType']


@dataclass(init=False)
class WayType:
    """
    Share of a tour on a given way type, as reported in a tour summary.

    :param way_type: Type of the way, usually a :class:`kompy.constants.PossibleWayType`. Unknown types are kept
        as plain strings. Stored as :attr:`type`.
    :param amount: Fraction of the tour on this way type, between 0 and 1.
    :raises ValueError: If the amount is outside [0, 1].
    """

    type: PossibleWayType | str
    amount: float

    def __init__(self, way_type: str, amount: float) -> None:
        self.type = coerce_enum(PossibleWayType, way_type)
        self.amount = normalize_amount(amount)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build the way type from the API shape ``{"type": "wt#street", "amount": 0.25}``.

        :param data: One entry of ``summary.way_types``.
        :return: The parsed way type.
        :raises KeyError: If a key is missing.
        :raises ValueError: If the amount is outside [0, 1].
        """
        return cls(way_type=require_str(data, 'type'), amount=float(data['amount']))
