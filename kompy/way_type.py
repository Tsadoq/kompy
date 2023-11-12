from kompy.constants.way_type import PossibleWayType


class WayType:
    def __init__(
        self,
        way_type: str,
        amount: float,
    ):
        """
        Initialize the way type information.
        :param way_type: Type of the way.
        :param amount: Amount, must be greater than 0 and less than 1.
        """
        if way_type not in PossibleWayType.list_all():
            raise ValueError(f'Invalid way type provided: {way_type}. Please provide a valid way type.')
        if not (0 < amount < 1):
            raise ValueError('Amount must be greater than 0 and less than 1.')
        self.type = way_type
        self.amount = amount
