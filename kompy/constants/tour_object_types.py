from typing import (
    Final,
    List,
)


class TourObjectTypes:
    """
    Types of tour objects to be returned.
    """
    KOMPY: Final[str] = 'kompy'
    GPX: Final[str] = 'gpx'
    FIT: Final[str] = 'fit'

    @classmethod
    def list_all(cls) -> List[str]:
        """
        List all tour object types.
        :return: A list of all supported tour object types
        """
        return [
            getattr(cls, attr) for attr in dir(cls) if not attr.startswith('__') and not callable(getattr(cls, attr))
        ]
