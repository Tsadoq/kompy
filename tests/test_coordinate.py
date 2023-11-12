import unittest

from kompy import Coordinate


class TestCoordinate(unittest.TestCase):

    def test_valid_initialization(self):
        """
        Test initialization of the Coordinate object.
        """
        coord = Coordinate(30, 40, 500, 1000)
        self.assertEqual(coord.lat, 30)
        self.assertEqual(coord.lon, 40)
        self.assertEqual(coord.alt, 500)
        self.assertEqual(coord.time, 1000)

    def test_initialization_without_optional_params(self):
        """
        Test initialization of the Coordinate object without optional parameters.
        """
        coord = Coordinate(30, 40)
        self.assertEqual(coord.lat, 30)
        self.assertEqual(coord.lon, 40)
        self.assertIsNone(coord.alt)
        self.assertIsNone(coord.time)

    def test_invalid_latitude(self):
        """
        Test invalid latitude values.
        """
        with self.assertRaises(ValueError):
            Coordinate(91, 40)
        with self.assertRaises(ValueError):
            Coordinate(-91, 40)

    def test_invalid_longitude(self):
        """
        Test invalid longitude values.
        """
        with self.assertRaises(ValueError):
            Coordinate(30, 181)
        with self.assertRaises(ValueError):
            Coordinate(30, -181)

    def test_invalid_altitude(self):
        """
        Test invalid altitude values.
        """
        with self.assertRaises(ValueError):
            Coordinate(30, 40, 10001)
        with self.assertRaises(ValueError):
            Coordinate(30, 40, -10001)

    def test_invalid_time(self):
        """
        Test invalid time values.
        """
        with self.assertRaises(ValueError):
            Coordinate(30, 40, 500, -1)

    def test_edge_cases(self):
        """
        Test edge cases.
        """
        coord = Coordinate(90, 180)
        self.assertEqual(coord.lat, 90)
        self.assertEqual(coord.lon, 180)

        coord = Coordinate(-90, -180)
        self.assertEqual(coord.lat, -90)
        self.assertEqual(coord.lon, -180)

        coord = Coordinate(30, 40, 10000)
        self.assertEqual(coord.alt, 10000)

        coord = Coordinate(30, 40, -10000)
        self.assertEqual(coord.alt, -10000)

        coord = Coordinate(30, 40, 500, 0)
        self.assertEqual(coord.time, 0)


if __name__ == '__main__':
    unittest.main()
