from kompy.constants.surface import SurfaceType


class Surface:
    def __init__(
        self,
        surface_type: str,
        amount: float,
    ):
        """
        Initialize the surface information.
        :param surface_type: Type of the surface.
        :param amount: Amount, must be greater than 0 and less than 1.
        """
        if surface_type not in SurfaceType.list_all():
            raise ValueError(f'Invalid surface type provided: {surface_type}. Please provide a valid surface type.')
        if not (0 <= amount <= 1):
            raise ValueError('Amount must be greater than 0 and less than 1.')
        self.type = surface_type
        self.amount = amount
