import unittest

from kompy import Difficulty
from kompy.constants import DifficultyGrade


class TestDifficulty(unittest.TestCase):

    def test_valid_initialization(self):
        """
        Test initialization of the Difficulty object.
        """
        valid_grade = DifficultyGrade.list_all()[0]
        difficulty = Difficulty(valid_grade, "Technical explanation", "Fitness explanation")
        self.assertEqual(difficulty.grade, valid_grade)
        self.assertEqual(difficulty.technical_explanation, "Technical explanation")
        self.assertEqual(difficulty.fitness_explanation, "Fitness explanation")

    def test_invalid_grade_initialization(self):
        """
        Test initialization of the Difficulty object with an invalid grade.
        """
        invalid_grade = "Not a valid grade"
        with self.assertRaises(ValueError):
            Difficulty(invalid_grade, "Technical explanation", "Fitness explanation")

    def test_edge_cases_for_grade(self):
        """
        Test edge cases for the grade.
        """
        for grade in DifficultyGrade.list_all():
            difficulty = Difficulty(grade, "Technical explanation", "Fitness explanation")
            self.assertEqual(difficulty.grade, grade)


if __name__ == '__main__':
    unittest.main()
