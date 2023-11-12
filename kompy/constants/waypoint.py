from typing import Optional

from kompy.coordinate import Coordinate


class Waypoint:
    def __init__(
        self,
        location: Coordinate,
        index: int,
        end_index: Optional[int] = None,
        reference: Optional[str] = None,
    ):
        """
        Initialize a Waypoint object.
        :param location: Location of the waypoint as a Coordinate object.
        :param index: Index into the tour coordinates array representing the location of the waypoint.
        :param end_index: Exclusive index into the tour coordinates array representing the location of the waypoint.
        :param reference: Reference to a highlight or OSM POI (optional), e.g., "hl:85124".
        """
        self.location = location
        self.index = index
        self.end_index = end_index
        self.reference = reference
