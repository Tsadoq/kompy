import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from dateutil import parser
from pydantic import BaseModel

from kompy.constants.activities import SupportedActivities
from kompy.constants.segment import Segment
from kompy.constants.tour_constants import SmartTourTypes
from kompy.constants.waypoint import Waypoint
from kompy.coordinate import Coordinate
from kompy.image import KomootImage


class SegmentInformation(BaseModel):
    """
    Segment Information.
    """
    start_index_point: int
    end_index_point: int


class TourInformation(BaseModel):
    """
    Tour Information.
    """
    tour_information_type: str
    segments: List[SegmentInformation]


class Tour(BaseModel):
    tour: Dict[str, Any]
    id: Optional[str]
    type: Optional[str]
    source: Optional[str]
    start_date: datetime
    changed_at: datetime
    name: Optional[str]
    kcal_active: Optional[int]
    kcal_resting: Optional[int]
    start_point: Coordinate
    distance: Optional[int]
    total_duration: Optional[int]
    elevation_up: Optional[int]
    elevation_down: Optional[int]
    sport: Optional[str]
    vector_map_image: Optional[KomootImage]
    time_in_motion: Optional[int]
    constitution: Optional[int]
    query: Optional[str]
    poor_quality: Optional[bool]
    smart_tour_type: Optional[str]
    path: Optional[List[Waypoint]]
    segments: Optional[List[Segment]]
    tour_information: Optional[List[TourInformation]]

    def load_from_dict(self, tour: Dict[str, Any]):
        self.tour = tour['_embedded']
        self.id = self.tour['id']
        self.type = self.tour['type']
        if 'source' in self.tour:
            self.source = self.tour['source']
        else:
            self.source = None
        self.start_date = parser.parse(tour['date'])
        self.changed_at = parser.parse(tour['changed_at'])
        self.name = tour['name']
        self.kcal_active = tour['kcal_active']
        self.kcal_resting = tour['kcal_resting']
        self.start_point = Coordinate(
            lat=tour['start_point']['lat'],
            lon=tour['start_point']['lng'],
            alt=tour['start_point']['alt'],
            time=tour['start_point']['time'],
        )
        self.distance = tour['distance']
        self.total_duration = tour['duration']
        self.elevation_up = tour['elevation_up']
        self.elevation_down = tour['elevation_down']
        if tour['sport'] not in SupportedActivities.list_all():
            raise ValueError(f'Invalid sport type provided: {tour["sport"]}. Please provide a valid sport type.')
        else:
            self.sport = tour['sport']
        if 'vector_map_image' in tour:
            self.vector_map_image = KomootImage(
                src=tour['vector_map_image']['src'],
                templated=tour['vector_map_image']['templated'] if 'templated' in tour['vector_map_image'] else None,
                client_hash=tour['vector_map_image']['client_hash'] if 'client_hash' in tour[
                    'vector_map_image'] else None,
                attribution=tour['vector_map_image']['attribution'] if 'attribution' in tour[
                    'vector_map_image'] else None,
                attribution_url=tour['vector_map_image']['attribution_url'] if ('attribution_url' in
                                                                                tour['vector_map_image']) else None,
                type=tour['vector_map_image']['type'] if 'type' in tour['vector_map_image'] else None,
            )
        else:
            self.vector_map_image = None
            logging.warning('No vector map image found.')
        self.time_in_motion = tour['time_in_motion'] if 'time_in_motion' in tour else None
        self.constitution = tour['constitution'] if 'constitution' in tour else None
        self.query = tour['query'] if 'query' in tour else None
        if 'smart_tour_type' in tour:
            if tour['smart_tour_type'] not in SmartTourTypes.list_all():
                raise ValueError(
                    f'Invalid smart tour type provided: {tour["smart_tour_type"]}. '
                    f'Please provide one of {SmartTourTypes.list_all()}.')
            else:
                self.smart_tour_type = tour['smart_tour_type'] if 'smart_tour_type' in tour else None
        self.poor_quality = tour['poor_quality'] if 'poor_quality' in tour else None
        self.path = self._create_list_waypoints(tour['path']) if 'path' in tour else None
        self.segments = self._create_list_segments(tour['segments']) if 'segments' in tour else None
        self.tour_information = self._create_tour_information(
            tour_information_array=tour['tour_information'],
        ) if 'tour_information' in tour else None

    @staticmethod
    def _create_list_waypoints(path: List[Dict[str, Any]]) -> List[Waypoint]:
        """
        Create a list of waypoints from the path.
        :param path: the path
        :return: a list of waypoints
        """
        waypoints = []
        for waypoint in path:
            waypoints.append(
                Waypoint(
                    location=Coordinate(
                        lat=waypoint['lat'],
                        lon=waypoint['lon'],
                    ),
                    index=waypoint['index'],
                    end_index=waypoint['end_index'] if 'end_index' in waypoint else None,
                    refernce=waypoint['reference'] if 'reference' in waypoint else None,
                )
            )
        return waypoints

    @staticmethod
    def _create_list_segments(segments: List[Dict[str, Any]]) -> List[Segment]:
        """
        Create a list of segments from the segments.
        :param segments: the segments
        :return: a list of segments
        """
        segments_list = []
        for segment in segments:
            segments_list.append(
                Segment(
                    segment_type=segment['type'],
                    segment_boundaries=SegmentInformation(
                        start_index_point=segment['index'],
                        end_index_point=segment['end_index'] if 'end_index' in segment else None,
                    ),
                    reference=segment['reference'] if 'reference' in segment else None,
                )
            )
        return segments_list

    @staticmethod
    def _create_tour_information(tour_information_array: List[Dict[str, Any]]) -> List[TourInformation]:
        """
        Create a list of tour information from the tour information array.
        :param tour_information_array:
        :return: List of TourInformation objects
        """

        tour_information_list = []
        for tour_information in tour_information_array:
            tour_information_list.append(
                TourInformation(
                    tour_information_type=tour_information['type'],
                    segments=[
                        SegmentInformation(
                            start_index_point=segment['index'],
                            end_index_point=segment['end_index'] if 'end_index' in segment else None,
                        ) for segment in tour_information['segments']
                    ],
                )
            )
        return tour_information_list
