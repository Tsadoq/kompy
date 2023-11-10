import logging
from io import BytesIO
from typing import Optional

import requests
from PIL import Image
from pydantic import BaseModel


class KomootImage(BaseModel):
    """
    Image object.
    :param image_url: link to the image
    :param templated: weather the link contains template variables
    :param client_hash: A hash set by the client on upload, useful for de-duplicating images
    :param attribution: if set, client must show attribution text
    :param attribution_url: if it exist, contains link to the attribution source
    :param type: media type of resource
    """
    image_url: str
    templated: bool
    client_hash: Optional[str]
    attribution: Optional[str]
    attribution_url: Optional[str]
    type: Optional[str]
    image: Optional[Image.Image]

    def load_image(self):
        """
        Load the image from the image url.
        """
        try:
            self.image = Image.open(BytesIO(requests.get(self.image_url).content))
        except requests.exceptions.ConnectionError:
            logging.error(f'Connection to {self.image_url} failed. Please check your internet connection.')
