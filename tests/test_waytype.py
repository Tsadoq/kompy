import unittest

from kompy import WayType
from kompy.constants.way_type import PossibleWayType


class TestWayType(unittest.TestCase):

    def test_initialization_with_valid_data(self):
        """
        Test initialization with valid way type and amount
        """
        for way_type in PossibleWayType.list_all():
            way_type_instance = WayType(way_type, 0.5)
            self.assertIsInstance(way_type_instance, WayType)
            self.assertEqual(way_type_instance.type, way_type)
            self.assertEqual(way_type_instance.amount, 0.5)

    def test_initialization_with_invalid_way_type(self):
        """
        Test initialization with an invalid way type
        """
        invalid_way_type = "invalid_type"
        with self.assertRaises(ValueError):
            WayType(invalid_way_type, 0.5)

    def test_initialization_with_invalid_amount(self):
        """
        Test initialization with invalid amounts (less than 0, equal to 0, greater than 1)
        """
        valid_way_type = PossibleWayType.list_all()[0]
        for amount in [-1, 0, 1, 2]:
            with self.assertRaises(ValueError):
                WayType(valid_way_type, amount)


if __name__ == '__main__':
    unittest.main()
