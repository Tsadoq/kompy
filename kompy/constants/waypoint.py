from typing import Optional

from pydantic import BaseModel

from kompy.coordinate import Coordinate


class Waypoint(BaseModel):
    """
    A waypoint of a planned tour. May be a manually inserted waypoint, a highlight or an OSM POI.

    :param location: location of the waypoint
    :param index: An index (inclusive) into the tour coordinates array representing the location of the waypoint
    along the tour.
    :param end_index: An index (exclusive) into the tour coordinates array representing the location of the waypoint
    along the tour.
    :param reference: A namespaced reference to a highlight or OSM POI, e.g. "hl:85124"
    """
    location: Coordinate
    index: int
    end_index: Optional[int]
    reference: Optional[str]
