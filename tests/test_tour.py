import os
import unittest

from kompy import (
    Coordinate,
    KomootConnector,
)


class TestTour(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Set up the KomootConnector for the tests.
        """
        cls.email = os.environ['KOMOOT_EMAIL']
        cls.password = os.environ['KOMOOT_PASSWORD']
        cls.connector = KomootConnector(email=cls.email, password=cls.password)
        cls.valid_id = os.environ['KOMOOT_VALID_TOUR_ID']
        cls.tour_obj = cls.connector.get_tour_by_id(cls.valid_id)

    def test_no_coordinates_before_get_coordinates(self):
        """
        Test the get_coordinates method.
        """
        empty_coord_tour = self.connector.get_tour_by_id(self.valid_id)
        self.assertEqual(empty_coord_tour.coordinates, [])

    def test_get_coordinates(self):
        """
        Test the get_coordinates method.
        """
        result = self.tour_obj.get_coordinates(authentication=self.connector.authentication)
        self.assertIsInstance(self.tour_obj.coordinates[0], Coordinate)
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
