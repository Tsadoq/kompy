import logging
from io import BytesIO
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger('KomootImage')
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


class KomootImage:
    def __init__(
        self,
        image_url: str,
        templated: bool,
        client_hash: Optional[str] = None,
        attribution: Optional[str] = None,
        attribution_url: Optional[str] = None,
        media_type: Optional[str] = None,
    ):
        """
        Initialize the KomootImage.
        :param image_url: Link to the image.
        :param templated: Whether the link contains template variables.
        :param client_hash: A hash set by the client on upload, useful for de-duplicating images.
        :param attribution: If set, client must show attribution text.
        :param attribution_url: If it exists, contains link to the attribution source.
        :param media_type: Media type of resource.
        """
        self.image_url = image_url
        self.templated = templated
        self.client_hash = client_hash
        self.attribution = attribution
        self.attribution_url = attribution_url
        self.media_type = media_type
        self.image = None

    def load_image(self):
        """
        Load the image from the image url.
        """
        try:
            response = requests.get(self.image_url)
            response.raise_for_status()
            self.image = Image.open(BytesIO(response.content))
        except requests.exceptions.HTTPError as http_err:
            logging.error(f'HTTP error occurred: {http_err}')
        except requests.exceptions.ConnectionError:
            logging.error(f'Connection to {self.image_url} failed. Please check your internet connection.')
        except requests.exceptions.RequestException as e:
            logging.error(f'Request error: {e}')
