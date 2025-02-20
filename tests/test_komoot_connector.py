import os
import unittest
from unittest.mock import patch, MagicMock
import gpxpy

from kompy import KomootConnector, Tour
from kompy.constants.privacy_status import PrivacyStatus
from tests.resources.mock_response_builder import mock_response_builder


class TestKomootConnector(unittest.TestCase):

    @classmethod
    @patch('requests.get')
    def setUpClass(cls, mock_get: MagicMock):
        cls.email = 'test@example.com'
        cls.password = 'password'
        cls.valid_id = '12345'
        cls.invalid_id = 'invalid_id'
        mock_response_builder(
            mock_get=mock_get,
            mock_status_code=200,
            json_file_path=f'{os.path.dirname(os.path.realpath(__file__))}/resources/authentication_response.json',
        )
        cls.connector = KomootConnector(
            email='test@example.com',
            password='password',
        )

    @patch('requests.get')
    def test_initialization(self, mock_get: MagicMock):
        mock_response_builder(
            mock_get=mock_get,
            mock_status_code=200,
            json_file_path=f'{os.path.dirname(os.path.realpath(__file__))}/resources/authentication_response.json',
        )
        connector = KomootConnector(
            email=self.email,
            password=self.password,
        )
        self.assertIsInstance(connector, KomootConnector)

    @patch('requests.get')
    def test_get_tours(self, mock_get):
        mock_response_builder(
            mock_get=mock_get,
            mock_status_code=200,
            json_file_path=f'{os.path.dirname(os.path.realpath(__file__))}/resources/fetch_tours.json',
        )

        tours = self.connector.get_tours(limit=10)
        self.assertIsInstance(tours, list)
        for tour in tours:
            self.assertIsInstance(tour, Tour)
        self.assertEqual(len(tours), 10)

    @patch('requests.get')
    def test_get_tour_by_valid_id(self, mock_get):
        mock_response_builder(
            mock_get=mock_get,
            mock_status_code=200,
            json_file_path=f'{os.path.dirname(os.path.realpath(__file__))}/resources/get_tour_by_id_response.json',
        )
        tour = self.connector.get_tour_by_id(tour_identifier=self.valid_id)
        self.assertIsInstance(tour, Tour)

    @patch('requests.post')
    def test_upload_tour(self, mock_get: MagicMock):
        mock_response_builder(
            mock_get=mock_get,
            mock_status_code=201,
            json_file_path=f'{os.path.dirname(os.path.realpath(__file__))}/resources/dummy_response_with_id.json',
        )
        gpx_data = gpxpy.parse(open(f'{os.path.dirname(os.path.realpath(__file__))}/resources/example.gpx'))
        ret = self.connector.upload_tour(gpx_data, "Example gpx", "hike", PrivacyStatus.PRIVATE)
        self.assertEqual(ret, True)

    @patch('requests.patch')
    def test_change_tour(self, mock_get: MagicMock):
        mock_response_builder(
            mock_get=mock_get,
            mock_status_code=200,
            json_file_path=f'{os.path.dirname(os.path.realpath(__file__))}/resources/dummy_response_with_id.json',
        )
        ret = self.connector.change_tour(self.valid_id, "test name", "test type", PrivacyStatus.PRIVATE)
        self.assertEqual(ret, True)

    @patch('requests.delete')
    def test_delete_tour(self, mock_get: MagicMock):
        mock_response_builder(
            mock_get=mock_get,
            mock_status_code=200,
            json_file_path=f'{os.path.dirname(os.path.realpath(__file__))}/resources/dummy_response_with_id.json',
        )
        ret = self.connector.delete_tour(self.valid_id)
        self.assertEqual(ret, True)


if __name__ == '__main__':
    unittest.main()
