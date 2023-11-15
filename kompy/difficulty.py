from kompy.constants.difficulty_grade import DifficultyGrade


class Difficulty:
    def __init__(self, grade: str, technical_explanation: str, fitness_explanation: str):
        """
        Initialize the difficulty information.
        :param grade: Difficulty grade.
        :param technical_explanation: Technical explanation of the difficulty.
        :param fitness_explanation: Fitness explanation of the difficulty.
        """
        if grade not in DifficultyGrade.list_all():
            raise ValueError(f'Invalid difficulty grade provided: {grade}. Please provide a valid difficulty grade.')
        self.grade: str = grade
        self.technical_explanation: str = technical_explanation
        self.fitness_explanation: str = fitness_explanation
