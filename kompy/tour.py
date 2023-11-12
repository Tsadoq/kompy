import logging
from typing import (
    Any,
    Dict,
    List,
)

import requests
from dateutil import parser

from kompy.authentication import Authentication
from kompy.constants.activities import SupportedActivities
from kompy.constants.tour_constants import SmartTourTypes
from kompy.constants.waypoint import Waypoint
from kompy.coordinate import Coordinate
from kompy.difficulty import Difficulty
from kompy.image import KomootImage
from kompy.segment import (
    Segment,
    SegmentInformation,
)
from kompy.surface import Surface
from kompy.way_type import WayType

logger = logging.getLogger('KomootTour')
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class TourInformation:
    def __init__(self, tour_information_type: str, segments: List['SegmentInformation']):
        """
        Initialize the tour information.
        :param tour_information_type: Type of the tour information.
        :param segments: List of segment information.
        """
        self.tour_information_type = tour_information_type
        self.segments = segments


class TourSummary:
    def __init__(
        self,
        surfaces: List[Surface],
        way_types: List[WayType],
    ):
        """
        Initialize the tour summary.
        :param surfaces: List of surfaces.
        :param way_types: List of way types.
        """
        self.surfaces = surfaces
        self.way_types = way_types


class Tour:
    def __init__(
        self,
        tour: Dict[str, Any],
    ):
        """
        Representation of a tour.

        A representation with the list of the native fields can be found at:
        https://static.komoot.de/doc/external-api/v007/docson/index.html#../schemas/users_tours.schema.json

        It contains the following attributes:
        - id: the id of the tour
        - type: the type of the tour
        - source: the source of the tour
        - start_date: the start date of the tour
        - changed_at: the date the tour was changed at
        - name: the name of the tour
        - kcal_active: the active kcal of the tour
        - kcal_resting: the resting kcal of the tour
        - start_point: the start point of the tour
        - distance: the distance of the tour, in meters
        - total_duration: the total duration of the tour, in seconds
        - elevation_up: the elevation up of the tour
        - elevation_down: the elevation down of the tour
        - sport: the sport type of the tour
        - vector_map_image: the vector map image of the tour
        - time_in_motion: the time in motion of the tour, in seconds
        - constitution: the constitution of the tour
        - query: the query of the tour
        - poor_quality: SEO info, the quality of creation of the tour
        - smart_tour_type: the smart tour type of the tour
        - path: the path of the tour
        - segments: the segments of the tour
        - tour_information: the tour information of the tour
        - tour_summary: the tour summary of the tour
        - difficulty: the difficulty of the tour
        - master_share_url: the master share url of the tour
        :param tour: the tour dictionary
        :return: None
        """
        self.id = tour['id']
        self.type = tour['type']
        if 'source' in tour:
            self.source = tour['source']
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
            time=None,
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
                image_url=tour['vector_map_image']['src'],
                templated=tour['vector_map_image']['templated'] if 'templated' in tour['vector_map_image'] else None,
                client_hash=tour['vector_map_image']['client_hash'] if 'client_hash' in tour[
                    'vector_map_image'] else None,
                attribution=tour['vector_map_image']['attribution'] if 'attribution' in tour[
                    'vector_map_image'] else None,
                attribution_url=tour['vector_map_image']['attribution_url'] if ('attribution_url' in
                                                                                tour['vector_map_image']) else None,
                media_type=tour['vector_map_image']['type'] if 'type' in tour['vector_map_image'] else None,
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
        self.tour_summary = self._create_tour_summary(tour['tour_summary']) if 'tour_summary' in tour else None
        self.difficulty = Difficulty(
            grade=tour['difficulty']['grade'],
            technical_explanation=tour['difficulty']['explanation_technical'],
            fitness_explanation=tour['difficulty']['explanation_fitness'],
        ) if 'difficulty' in tour else None
        self.master_share_url = tour['master_share_url'] if 'master_share_url' in tour else None
        self.links_dict = tour['_links'] if '_links' in tour else None
        if self.links_dict is not None:
            self.coordinates_link = self.links_dict['coordinates']['href'] if 'coordinates' in self.links_dict else None
        self.coordinates = []

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
                        lat=waypoint['location']['lat'],
                        lon=waypoint['location']['lng'],
                    ),
                    index=waypoint['index'],
                    end_index=waypoint['end_index'] if 'end_index' in waypoint else None,
                    reference=waypoint['reference'] if 'reference' in waypoint else None,
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
                        start_index_point=segment['from'],
                        end_index_point=segment['to'],
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
                            start_index_point=segment['from'],
                            end_index_point=segment['to'],
                        ) for segment in tour_information['segments']
                    ],
                )
            )
        return tour_information_list

    @staticmethod
    def _create_tour_summary(tour_summary: Dict[str, Any]) -> TourSummary:
        """
        Create a tour summary from the tour summary.
        :param tour_summary: the tour summary
        :return: a TourSummary object
        """
        return TourSummary(
            surfaces=[
                Surface(
                    surface_type=surface['type'],
                    amount=surface['amount'],
                ) for surface in tour_summary['surfaces']
            ],
            way_types=[
                WayType(
                    way_type=way_type['type'],
                    amount=way_type['amount'],
                ) for way_type in tour_summary['way_types']
            ],
        )

    def get_coordinates(self, authentication: Authentication) -> bool:
        """
        Fetch the coordinates of the tour.
        :param authentication: The authentication object.
        :return: True if the coordinates were fetched successfully, False otherwise
        """
        if self.coordinates_link is not None:
            coord_request = requests.get(
                url=self.coordinates_link,
                auth=(authentication.get_email_address(), authentication.get_password()),
            ).json()['items']
        else:
            logging.warning('No coordinates link found.')
            return False

        self.coordinates = [
            Coordinate(
                lat=coord_dict['lat'],
                lon=coord_dict['lng'],
                alt=coord_dict['alt'],
                time=coord_dict['t'],
            ) for coord_dict in coord_request
        ]

        return True
