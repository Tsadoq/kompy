import unittest
from unittest.mock import (
    Mock,
    patch,
)

import requests

from kompy import KomootImage


class TestKomootImage(unittest.TestCase):

    @patch('requests.get')  # Patch requests.get specifically in the KomootImage context
    @patch('PIL.Image.open')  # Patch Image.open specifically in the KomootImage context
    def test_load_image_success(self, mock_open, mock_get):
        # Mock the response of requests.get
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'image_data'
        mock_get.return_value = mock_response

        # Create an instance of KomootImage
        komoot_image = KomootImage("https://picsum.photos/200", False)

        # Call load_image
        komoot_image.load_image()

        # Check if the image attribute is set
        self.assertIsNotNone(komoot_image.image)

    @patch('requests.get')  # Patch requests.get specifically in the KomootImage context
    def test_load_image_failure(self, mock_get):
        # Simulate an HTTPError
        mock_get.side_effect = requests.exceptions.HTTPError()

        # Create an instance of KomootImage
        komoot_image = KomootImage("http://example.com/image.jpg", False)

        # Call load_image and expect no image to be set
        komoot_image.load_image()
        self.assertIsNone(komoot_image.image)


if __name__ == '__main__':
    unittest.main()
