import os
import unittest

from kompy import (
    KomootConnector,
    Tour,
)


class TestKomootConnector(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Set up the KomootConnector for the tests.
        """
        cls.email = os.environ['KOMOOT_EMAIL']
        cls.password = os.environ['KOMOOT_PASSWORD']
        cls.connector = KomootConnector(email=cls.email, password=cls.password)
        cls.valid_id = os.environ['KOMOOT_VALID_TOUR_ID']
        cls.invalid_id = 'your_invalid_id'

    def test_initialization(self):
        """
        Test initialization of the KomootConnector.
        """
        self.assertIsInstance(self.connector, KomootConnector)

    def test_connect_is_populated(self):
        """
        Test if the connect attribute is populated.
        """
        self.assertIsNotNone(self.connector.authentication.get_email_address())
        self.assertIsNotNone(self.connector.authentication.get_token())

    def test_get_tours(self):
        """
        Test the get_tours method.
        """
        tours = self.connector.get_tours(limit=10)
        self.assertIsInstance(tours, list)
        for tour in tours:
            self.assertIsInstance(tour, Tour)
        self.assertEqual(len(tours), 10)

    def test_get_tour_by_valid_id(self):
        """
        Test the get_tour_by_id method with a valid id.
        """
        tour = self.connector.get_tour_by_id(self.valid_id)
        self.assertIsInstance(tour, Tour)

    def test_get_tour_by_invalid_id(self):
        """
        Test the get_tour_by_id method with an invalid id.
        """
        with self.assertRaises(ValueError):
            self.connector.get_tour_by_id(self.invalid_id)


if __name__ == '__main__':
    unittest.main()
