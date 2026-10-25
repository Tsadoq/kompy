"""Difficulty of a planned tour."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kompy._parsing import coerce_enum, optional_str, require_str
from kompy.constants.difficulty_grade import DifficultyGrade

__all__ = ['Difficulty']


@dataclass
class Difficulty:
    """
    Difficulty information of a planned tour.

    :param grade: Difficulty grade, usually a :class:`kompy.constants.DifficultyGrade`. Unknown grades are kept
        as plain strings.
    :param technical_explanation: Komoot code explaining the technical difficulty (e.g. ``'dj#t3'``).
    :param fitness_explanation: Komoot code explaining the required fitness (e.g. ``'d#c3'``).
    """

    grade: DifficultyGrade | str
    technical_explanation: str | None = None
    fitness_explanation: str | None = None

    def __post_init__(self) -> None:
        self.grade = coerce_enum(DifficultyGrade, self.grade)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build the difficulty from the API shape ``{"grade", "explanation_technical", "explanation_fitness"}``.

        :param data: The ``difficulty`` payload of a tour.
        :return: The parsed difficulty.
        :raises KeyError: If ``grade`` is missing.
        """
        return cls(
            grade=require_str(data, 'grade'),
            technical_explanation=optional_str(data.get('explanation_technical')),
            fitness_explanation=optional_str(data.get('explanation_fitness')),
        )
