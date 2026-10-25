"""Images hosted by Komoot (map previews, avatars, highlight photos, ...)."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from io import BytesIO
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from kompy._parsing import optional_bool, optional_str, require_str

if TYPE_CHECKING:
    from PIL import Image as PILImage

__all__ = ['KomootImage']

logger = logging.getLogger(__name__)

#: Default timeout in seconds for downloading an image.
DEFAULT_IMAGE_TIMEOUT = 10.0

_PLACEHOLDER = re.compile(r'\{(?P<name>\w+)\}')


@dataclass
class KomootImage:
    """
    An image hosted by Komoot.

    Some image URLs are *templated*: they contain ``{width}``, ``{height}`` and ``{crop}`` placeholders that must be
    filled in before downloading. Use :meth:`url_for` to get a concrete URL.

    :param image_url: Link to the image (possibly templated).
    :param templated: Whether the link contains template placeholders.
    :param client_hash: A hash set by the client on upload, useful for de-duplicating images.
    :param attribution: If set, the attribution text that must be shown with the image.
    :param attribution_url: Link to the attribution source, if any.
    :param media_type: Media type of the resource, e.g. ``'image/*'``.
    """

    image_url: str
    templated: bool = False
    client_hash: str | None = None
    attribution: str | None = None
    attribution_url: str | None = None
    media_type: str | None = None
    image: PILImage.Image | None = field(default=None, init=False, repr=False, compare=False)
    """The downloaded image, set by :meth:`load_image`."""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build an image from the API shape ``{"src", "templated"?, "type"?, "client_hash"?, "attribution"?, ...}``.

        :param data: The image payload.
        :return: The parsed image.
        :raises KeyError: If ``src`` is missing.
        """
        return cls(
            image_url=require_str(data, 'src'),
            templated=optional_bool(data.get('templated')) or False,
            client_hash=optional_str(data.get('client_hash')),
            attribution=optional_str(data.get('attribution')),
            attribution_url=optional_str(data.get('attribution_url')),
            media_type=optional_str(data.get('type')),
        )

    def url_for(self, width: int | None = None, height: int | None = None, crop: bool | None = None) -> str:
        """
        Get a concrete URL for the image, filling in the template placeholders.

        Query parameters whose placeholder has no value are dropped, so the server uses its default.
        Non-templated URLs are returned unchanged.

        :param width: Requested width in pixels.
        :param height: Requested height in pixels.
        :param crop: Whether the server should crop the image to exactly ``width`` x ``height``.
        :return: The URL to download.
        """
        if not self.templated:
            return self.image_url
        values = {
            'width': None if width is None else str(width),
            'height': None if height is None else str(height),
            'crop': None if crop is None else str(crop).lower(),
        }
        parts = urlsplit(self.image_url)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            placeholder = _PLACEHOLDER.fullmatch(value)
            if placeholder is None:
                query.append((key, value))
            elif (replacement := values.get(placeholder['name'])) is not None:
                query.append((key, replacement))
        return urlunsplit(parts._replace(query=urlencode(query)))

    def load_image(
        self,
        width: int | None = None,
        height: int | None = None,
        *,
        timeout: float = DEFAULT_IMAGE_TIMEOUT,
    ) -> PILImage.Image | None:
        """
        Download the image and store it in :attr:`image`.

        Download and decoding failures are logged (on the ``kompy.image`` logger) rather than raised, and leave
        :attr:`image` unchanged. Requires the optional Pillow dependency: ``pip install 'kompy[images]'``.

        :param width: Requested width in pixels, for templated images.
        :param height: Requested height in pixels, for templated images.
        :param timeout: Timeout in seconds for the download.
        :return: The loaded image, or ``None`` if it could not be loaded.
        :raises ImportError: If Pillow is not installed.
        """
        try:
            from PIL import Image  # noqa: PLC0415 - Pillow is an optional dependency
        except ImportError as error:
            raise ImportError("Loading images requires Pillow. Install it with: pip install 'kompy[images]'") from error

        url = self.url_for(width=width, height=height)
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            self.image = Image.open(BytesIO(response.content))
        except requests.RequestException as error:
            logger.warning('Could not download image %s: %s', url, error)
            return None
        except OSError as error:  # Pillow raises UnidentifiedImageError (an OSError) for undecodable data
            logger.warning('Could not decode image %s: %s', url, error)
            return None
        return self.image
