"""Difficulty grades of planned tours."""

from __future__ import annotations

from kompy.constants._base import KomootStrEnum

__all__ = ['DifficultyGrade']


class DifficultyGrade(KomootStrEnum):
    """Overall difficulty grade that Komoot assigns to a planned tour."""

    EASY = 'easy'
    MODERATE = 'moderate'
    DIFFICULT = 'difficult'
