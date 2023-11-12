import json
import logging
import re
from typing import (
    List,
    Optional,
    Union,
    Any,
    Dict,
)

import dateutil.parser as parser
import gpxpy
import requests
from fit_tool.fit_file import FitFile
from gpxpy.gpx import GPX

from kompy.authentication import Authentication
from kompy.constants.activities import SupportedActivities
from kompy.constants.privacy_status import PrivacyStatus
from kompy.constants.query_parameters import TourQueryParameters
from kompy.constants.tour_constants import (
    TourSort,
    TourSortField,
    TourTypes,
)
from kompy.constants.tour_object_types import TourObjectTypes
from kompy.constants.urls import KomootUrl
from kompy.errors.initialisation_errors import NotEmailError
from kompy.errors.privacy_errors import PrivacyError
from kompy.tour import Tour

logger = logging.getLogger('KomootConnector')
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class KomootConnector:

    def __init__(
        self,
        email: str,
        password: str,
    ):
        """
        Connector to Komoot API.
        :param email: email address used to log in to Komoot
        :param password: password used to log in to Komoot
        """
        if not re.match(
            pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b',
            string=email,
        ):
            raise NotEmailError(email)

        self.authentication = Authentication(
            email_address=email,
            password=password,
        )
        try:
            response = requests.get(
                url=KomootUrl.USER_LOGIN_URL.format(email_address=self.authentication.get_email_address()),
                auth=(self.authentication.get_email_address(), self.authentication.get_password()),
            )
            if response.status_code == 403:
                raise ConnectionError(
                    'Connection to Komoot API failed. Please check your credentials.'
                )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                'Connection to Komoot API failed. Please check your internet connection.'
            )
        self.authentication.set_token(
            token=response.json()['password']
        )
        self.authentication.set_username(
            username=json.loads(response.content.decode('utf-8'))['username']
        )
        logger.info(f'Logged in as {self.authentication.get_username()}.')

    def get_tours(
        self,
        limit: Optional[int] = None,
        user_identifier: Optional[str] = None,
        page: Optional[int] = None,
        status: Optional[str] = PrivacyStatus.PUBLIC,
        tour_type: Optional[str] = None,
        only_unlocked: Optional[bool] = False,
        center: Optional[str] = None,
        max_distance: Optional[int] = None,
        sport_types: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        tour_name: Optional[str] = None,
        sort: Optional[str] = None,
        sort_field: Optional[str] = None,
    ) -> List[Tour]:
        """
        Get a list of tours.
        :param limit: The maximum number of tours to retrieve, if not provided, all tours are returned
        :param user_identifier: The user identifier, if not provided, the logged in user is used
        :param page: The page to retrieve, if not provided, the first page is used
        :param status: The privacy status of the tour, if not provided, only public tours are returned
        :param tour_type: The tour type, if not provided, return all tours
        :param only_unlocked: Whether to only return unlocked tours, if not provided, return all tours
        :param center: The center of the search area, if not provided, return all tours
        :param max_distance: The maximum distance to the center, if not provided, return all tours
        :param sport_types: The sport types to filter by, if not provided, return all tours
        :param start_date: The start date to filter by, if not provided, return all tours
        :param end_date: The end date to filter by, if not provided, return all tours
        :param tour_name: The tour name to filter by, if not provided, return all tours
        :param sort: The sort direction, if not provided, return all tours
        :param sort_field: The field to sort by, if not provided, return all tours
        :return: A list of tour objects
        """
        if user_identifier is None:
            logger.warning(f'No user identifier provided, '
                           f'using the currently logged user: {self.authentication.get_username()}')
            user_identifier = self.authentication.get_username()
        if status is None:
            status = PrivacyStatus.PUBLIC
        if status is not PrivacyStatus.PUBLIC and self.authentication.get_username() != user_identifier:
            raise PrivacyError(user_identifier)
        if tour_type is not None and tour_type not in [TourTypes.TOUR_PLANNED, TourTypes.TOUR_RECORDED]:
            raise ValueError(f'Invalid tour type provided: {tour_type}. Please provide a valid tour type.')
        if center is not None:
            if not re.match(
                pattern=r'^[-+]?\d{1,2}(\.\d+)?,\s*[-+]?\d{1,3}(\.\d+)?$',
                string=center,
            ):
                raise ValueError(
                    f'Invalid center provided: {center}. '
                    f'Please provide a valid center in the format "lat, lon" (e.g. "52.520008, 13.404954").'
                )
        if max_distance is None and center is not None:
            raise ValueError('Max distance must be provided if center is provided.')
        if max_distance is not None and center is None:
            logger.warning('Max distance provided but no center, ignoring max distance.')
        if sport_types is not None:
            if not isinstance(sport_types, list):
                raise TypeError(f'Invalid sport types provided: {sport_types}. Please provide a list of strings.')
            for sport_type in sport_types:
                if not isinstance(sport_type, str):
                    raise TypeError(f'Invalid sport type provided: {sport_type}. Please provide a string.')
                if sport_type not in SupportedActivities.list_all():
                    raise ValueError(f'Invalid sport type provided: {sport_type}. Please provide a valid sport type.')
        if start_date is not None:
            start_date = parser.parse(start_date)
        if end_date is not None:
            end_date = parser.parse(end_date)
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError(f'Start date ({start_date}) must be before end date ({end_date}).')
        if sort is not None and sort not in [TourSort.ASCENDING, TourSort.DESCENDING]:
            raise ValueError(f'Invalid sort provided: {sort}. Please provide a valid sort (can be '
                             f'{TourSort.ASCENDING} or {TourSort.DESCENDING}')
        if sort_field is not None and sort_field not in TourSortField.list_all():
            raise ValueError(f'Invalid sort field provided: {sort_field}. Please provide a valid sort field.')
        if not sort_field:
            logger.warning('No sort field provided, using default sort field: date')
        if sort_field == TourSortField.PROXIMITY and center is None:
            raise ValueError('Sort field proximity requires a center to be provided.')

        query_parameters = TourQueryParameters.construct_tour_query(
            limit=limit,
            page=page,
            status=status,
            tour_type=tour_type,
            only_unlocked=only_unlocked,
            center=center,
            max_distance=max_distance,
            sport_types=sport_types,
            start_date=start_date,
            end_date=end_date,
            name=tour_name,
            sort_direction=sort,
            sort_field=sort_field,
        )

        fetch_more = True
        current_page = 0
        tours = []
        while fetch_more:
            query_parameters[TourQueryParameters.PAGE] = current_page
            response = self._get_page_of_tours(
                query_parameters=query_parameters,
                user_identifier=user_identifier,
            ).json()
            tour_list = response['_embedded']
            tours.extend(tour_list['tours'])
            max_page = response['page']['totalPages']
            current_page = response['page']['number'] + 1
            logger.info(f'Fetched page {current_page} of {max_page}.')
            fetch_more = (current_page < max_page) if limit is None else False
        tour_objects = [
            Tour(tour_dict) for tour_dict in tours
        ]
        return tour_objects

    def get_tour_by_id(
        self,
        tour_identifier: str,
        share_token: Optional[str] = None,
        object_type: Optional[str] = None,
    ) -> Union[Tour, GPX, FitFile]:
        """
        Get a tour by its ID.
        :param tour_identifier: The ID of the tour
        :param share_token: share token which always grants access to a specific tour, ignoring visibility rules.
        :param object_type: The type of tour object to return, if not provided, return the kompy object
        :return: A tour object, gpx object or fit object depending on the object type provided
        """

        params = {
            'Type': 'application/hal+json',
        }
        if share_token:
            params['share_token'] = share_token

        if not object_type or object_type == TourObjectTypes.KOMPY:
            format_append = ''
        elif object_type == TourObjectTypes.GPX:
            format_append = '.gpx'
        elif object_type == TourObjectTypes.FIT:
            format_append = '.fit'
        else:
            raise ValueError(f'Invalid object type provided: {object_type}. Please provide a valid object type.')

        try:
            response = requests.get(
                url=KomootUrl.DOWNLOAD_TOUR_URL.format(tour_identifier=tour_identifier) + format_append,
                auth=(self.authentication.get_email_address(), self.authentication.get_password()),
                params=params,
            )
            if response.status_code == 403:
                raise ConnectionError(
                    'Connection to Komoot API failed. Please check your credentials.'
                )
            if response.status_code == 404:
                raise ValueError(f'Invalid tour identifier provided: {tour_identifier}. '
                                 f'Please provide a valid tour identifier.')
            if response.status_code == 500:
                raise ConnectionError(
                    'Internal Server Error. if you requested a FIT file, '
                    'please try again later or try fetching another format.'
                )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                'Connection to Komoot API failed. Please check your internet connection.'
            )
        if not object_type or object_type == TourObjectTypes.KOMPY:
            resp = json.loads(response.content.decode('utf-8'))
            return Tour(resp)
        if object_type == TourObjectTypes.GPX:
            return gpxpy.parse(response.content)
        if object_type == TourObjectTypes.FIT:
            return FitFile.from_bytes(response.content)

    def upload_tour(
        self,
        tour_object: Union[GPX, FitFile],
        activity_type: str,
        tour_name: str,
        time_in_motion: Optional[int] = None,
    ) -> bool:
        """
        Upload a tour. It can be either a GPX or FIT file.
        :param tour_object: The binary data of the file
        :param activity_type: The sport type, one of SupportedActivities
        :param tour_name: The name of the tour
        :param time_in_motion: Only exists for GPX files, in other file types this can be specified in the file itself.
        The time in motion in seconds. This is the time the user was active, so the overall duration minus the pauses.
        It must not be larger than the overall duration of the tour.
        :return: Whether the upload was successful
        """
        headers = {
            'User-Agent': 'Kompy',
        }
        params = {
            'sport': activity_type,
        }
        if isinstance(tour_object, GPX):
            params['data_type'] = 'gpx'
            params['time_in_motion'] = time_in_motion
        elif isinstance(tour_object, FitFile):
            params['data_type'] = 'fit'
        else:
            raise TypeError(f'Invalid tour object provided: {type(tour_object)}. Please provide a GPX or FIT file.')
        params['name'] = tour_name
        resp = requests.post(
            url=KomootUrl.UPLOAD_TOUR_URL.format(object_type=params['data_type']),
            auth=(self.authentication.get_email_address(), self.authentication.get_password()),
            headers=headers,
            params=params,
            data=tour_object.to_xml().encode('utf-8') if isinstance(tour_object, GPX) else tour_object.to_bytes()
        )
        if resp.status_code == 201:
            logging.info(f'Tour uploaded successfully with ID: {resp.json()["id"]}.')
            return True
        elif resp.status_code == 202:
            logging.warning(f'Tour not created due to the same tour being already present with ID: {resp.json()["id"]}')
            return True
        else:
            logging.error(f'Could not upload tour Failed: {resp.status_code}')
            return False

    def _get_page_of_tours(
        self,
        query_parameters: Dict[str, Any],
        user_identifier: str,
    ) -> requests.Response:
        """
        Get a page of tours.
        :param query_parameters: parameters to filter the tours by
        :param user_identifier: The user identifier
        :return: A page of tours as a response object
        """
        try:
            response = requests.get(
                url=KomootUrl.LIST_TOURS_URL.format(user_identifier=user_identifier),
                auth=(self.authentication.get_email_address(), self.authentication.get_password()),
                params=query_parameters,
            )
            if response.status_code == 403:
                raise ConnectionError(
                    'Connection to Komoot API failed. Please check your credentials.'
                )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                'Connection to Komoot API failed. Please check your internet connection.'
            )
        return response
