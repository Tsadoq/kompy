import unittest

from kompy import Surface
from kompy.constants import SurfaceType


class TestSurface(unittest.TestCase):

    def test_initialization_with_valid_inputs(self):
        """
        Test initialization with valid inputs
        """
        surface = Surface(surface_type=SurfaceType.PAVING_STONES_BIKE, amount=0.5)
        self.assertIsInstance(surface, Surface)
        self.assertEqual(surface.type, SurfaceType.PAVING_STONES_BIKE)
        self.assertEqual(surface.amount, 0.5)

    def test_initialization_with_invalid_surface_type(self):
        """
        Test initialization with an invalid surface type
        """
        with self.assertRaises(ValueError):
            Surface(surface_type='invalid_surface_type', amount=0.5)

    def test_initialization_with_invalid_amount_values(self):
        """
        Test initialization with invalid amount values
        """
        with self.assertRaises(ValueError):
            Surface(surface_type=SurfaceType.PAVING_STONES_BIKE, amount=-0.1)
        with self.assertRaises(ValueError):
            Surface(surface_type=SurfaceType.PAVING_STONES_BIKE, amount=1.1)

    def test_surface_properties(self):
        """
        Test the properties of the Surface
        """
        surface = Surface(surface_type=SurfaceType.PAVING_STONES_BIKE, amount=0.5)
        self.assertEqual(surface.type, SurfaceType.PAVING_STONES_BIKE)
        self.assertEqual(surface.amount, 0.5)


if __name__ == '__main__':
    unittest.main()
