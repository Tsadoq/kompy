"""Tests for :class:`kompy.Difficulty`."""

from __future__ import annotations

import pytest

from kompy import Difficulty
from kompy.constants import DifficultyGrade


@pytest.mark.parametrize('grade', DifficultyGrade.list_all())
def test_known_grades_become_enum_members(grade: str) -> None:
    difficulty = Difficulty(grade, 'Technical explanation', 'Fitness explanation')

    assert difficulty.grade == grade
    assert isinstance(difficulty.grade, DifficultyGrade)
    assert difficulty.technical_explanation == 'Technical explanation'
    assert difficulty.fitness_explanation == 'Fitness explanation'


def test_unknown_grade_is_kept_as_plain_string() -> None:
    difficulty = Difficulty('expert', 'dj#t6', 'd#c5')

    assert difficulty.grade == 'expert'
    assert not isinstance(difficulty.grade, DifficultyGrade)


def test_explanations_are_optional() -> None:
    difficulty = Difficulty(grade=DifficultyGrade.EASY)

    assert difficulty.technical_explanation is None
    assert difficulty.fitness_explanation is None


def test_from_dict() -> None:
    difficulty = Difficulty.from_dict(
        {'grade': 'difficult', 'explanation_technical': 'dj#t3', 'explanation_fitness': 'd#c3'}
    )

    assert difficulty == Difficulty(DifficultyGrade.DIFFICULT, 'dj#t3', 'd#c3')


def test_from_dict_without_explanations() -> None:
    difficulty = Difficulty.from_dict({'grade': 'easy'})

    assert difficulty == Difficulty('easy')


def test_from_dict_requires_grade() -> None:
    with pytest.raises(KeyError):
        Difficulty.from_dict({'explanation_technical': 'dj#t3'})
