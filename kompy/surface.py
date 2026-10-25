"""Share of a tour on a given surface."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kompy._parsing import coerce_enum, require_str
from kompy.constants.surface import SurfaceType

__all__ = ['Surface']

#: Amounts slightly outside [0, 1] are floating point noise from the API and are clamped instead of rejected.
AMOUNT_TOLERANCE = 1e-6


def normalize_amount(amount: float) -> float:
    """
    Validate a fraction in [0, 1], clamping values that are only off by rounding noise.

    :param amount: The fraction to check.
    :return: The fraction, clamped to [0, 1].
    :raises ValueError: If the fraction is clearly outside [0, 1].
    """
    if not -AMOUNT_TOLERANCE <= amount <= 1 + AMOUNT_TOLERANCE:
        raise ValueError(f'Amount must be between 0 and 1 (inclusive), got {amount}.')
    return min(max(float(amount), 0.0), 1.0)


@dataclass(init=False)
class Surface:
    """
    Share of a tour on a given surface, as reported in a tour summary.

    :param surface_type: Type of the surface, usually a :class:`kompy.constants.SurfaceType`. Unknown types are
        kept as plain strings. Stored as :attr:`type`.
    :param amount: Fraction of the tour on this surface, between 0 and 1.
    :raises ValueError: If the amount is outside [0, 1].
    """

    type: SurfaceType | str
    amount: float

    def __init__(self, surface_type: str, amount: float) -> None:
        self.type = coerce_enum(SurfaceType, surface_type)
        self.amount = normalize_amount(amount)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build the surface from the API shape ``{"type": "sf#asphalt", "amount": 0.25}``.

        :param data: One entry of ``summary.surfaces``.
        :return: The parsed surface.
        :raises KeyError: If a key is missing.
        :raises ValueError: If the amount is outside [0, 1].
        """
        return cls(surface_type=require_str(data, 'type'), amount=float(data['amount']))
