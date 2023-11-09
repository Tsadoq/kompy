import json
import logging
import re
from datetime import datetime
from typing import Optional, List

import requests

from kompy.constants.privacy_status import PrivacyStatus
from kompy.constants.urls import KomootUrl
from kompy.errors.initialisation_errors import NotEmailError


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
        else:
            self.email = email
        self.password = password
        try:
            response = requests.get(
                url=KomootUrl.USER_LOGIN_URL.format(email_address=self.email),
                auth=(self.email, self.password),
            )
            if response.status_code == 403:
                raise ConnectionError(
                    'Connection to Komoot API failed. Please check your credentials.'
                )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                'Connection to Komoot API failed. Please check your internet connection.'
            )
        self.token = response.json()['password']
        self.logged_username = json.loads(response.content.decode('utf-8'))['username']

    def get_tours(
        self,
        user_identifier: Optional[str] = None,
        page: Optional[int] = None,
        status: Optional[str] = PrivacyStatus.PUBLIC,
        only_unlocked: Optional[bool] = False,
        center: Optional[str] = None,
        max_distance: Optional[int] = None,
        sport_types: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        tour_name: Optional[str] = None,
        sort: Optional[str] = None,
        sort_field: Optional[str] = None,
    ):
        """
        Get a list of tours.
        :param user_identifier: The user identifier, if not provided, the logged in user is used
        :param page: The page to retrieve, if not provided, the first page is used
        :param status: The privacy status of the tour, if not provided, only public tours are returned
        :param only_unlocked: Whether to only return unlocked tours, if not provided, all tours are returned
        :param center: The center of the search area, if not provided, all tours are returned
        :param max_distance: The maximum distance to the center, if not provided, all tours are returned
        :param sport_types: The sport types to filter by, if not provided, all tours are returned
        :param start_date: The start date to filter by, if not provided, all tours are returned
        :param end_date: The end date to filter by, if not provided, all tours are returned
        :param tour_name: The tour name to filter by, if not provided, all tours are returned
        :param sort: The sort direction, if not provided, all tours are returned
        :param sort_field: The field to sort by, if not provided, all tours are returned
        :return: A list of tours
        """
        if user_identifier is None:
            logging.info(f'No user identifier provided, using the currently logged user: {self.logged_username}')
            user_identifier = self.logged_username
        if status is None:
            status = PrivacyStatus.PUBLIC
        if status is not PrivacyStatus.PUBLIC and self.logged_username != user_identifier:
            raise ValueError(
                'Only public tours can be retrieved for other users than the logged in user.'
            )
        if only_unlocked is None:
            only_unlocked = False
        if center is None:
            center = ''
        if max_distance is None:
            max_distance
