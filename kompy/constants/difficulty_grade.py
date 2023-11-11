from typing import List, Final


class DifficultyGrade:
    """
    Difficulty Grade.
    """
    EASY: Final[str] = 'easy'
    MODERATE: Final[str] = 'moderate'
    DIFFICULT: Final[str] = 'difficult'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all supported difficulty grades.
        :return: A list of all supported difficulty grades
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]
