"""Tests for :class:`kompy.KomootImage`."""

from __future__ import annotations

import logging
import sys
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses
from PIL import Image

from kompy import KomootImage

TEMPLATED_URL = 'https://images.example.com/photo/1?width={width}&height={height}&crop={crop}'
PLAIN_URL = 'https://images.example.com/photo/1'


def _png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new('RGB', (4, 3), color='red').save(buffer, format='PNG')
    return buffer.getvalue()


def test_constructor_defaults() -> None:
    image = KomootImage(PLAIN_URL)

    assert image.templated is False
    assert image.client_hash is None
    assert image.attribution is None
    assert image.attribution_url is None
    assert image.media_type is None
    assert image.image is None


def test_positional_constructor_is_backward_compatible() -> None:
    image = KomootImage(PLAIN_URL, True, 'hash', 'OSM', 'https://osm.org', 'image/*')

    assert (image.templated, image.client_hash, image.attribution) == (True, 'hash', 'OSM')
    assert (image.attribution_url, image.media_type) == ('https://osm.org', 'image/*')


def test_from_dict() -> None:
    image = KomootImage.from_dict(
        {
            'src': TEMPLATED_URL,
            'templated': True,
            'type': 'image/*',
            'attribution': 'Map data (c) OpenStreetMap contributors',
            'client_hash': 'abc',
        }
    )

    assert image == KomootImage(
        image_url=TEMPLATED_URL,
        templated=True,
        client_hash='abc',
        attribution='Map data (c) OpenStreetMap contributors',
        media_type='image/*',
    )


def test_from_dict_defaults_templated_to_false() -> None:
    assert KomootImage.from_dict({'src': PLAIN_URL}).templated is False
    assert KomootImage.from_dict({'src': PLAIN_URL, 'templated': None}).templated is False


def test_from_dict_requires_src() -> None:
    with pytest.raises(KeyError):
        KomootImage.from_dict({'templated': False})


def test_url_for_non_templated_url_is_unchanged() -> None:
    assert KomootImage(PLAIN_URL).url_for(width=100, height=100) == PLAIN_URL


def test_url_for_fills_all_placeholders() -> None:
    url = KomootImage(TEMPLATED_URL, templated=True).url_for(width=640, height=480, crop=True)

    assert url == 'https://images.example.com/photo/1?width=640&height=480&crop=true'


def test_url_for_drops_placeholders_without_value() -> None:
    url = KomootImage(TEMPLATED_URL, templated=True).url_for(width=200)

    assert url == 'https://images.example.com/photo/1?width=200'
    assert KomootImage(TEMPLATED_URL, templated=True).url_for() == PLAIN_URL


def test_url_for_keeps_regular_query_parameters() -> None:
    image = KomootImage('https://images.example.com/p?id=7&width={width}&crop={crop}', templated=True)

    assert parse_qs(urlsplit(image.url_for(width=10, crop=False)).query) == {
        'id': ['7'],
        'width': ['10'],
        'crop': ['false'],
    }


def test_load_image_success() -> None:
    image = KomootImage(TEMPLATED_URL, templated=True)
    with responses.RequestsMock() as mock:
        mock.get('https://images.example.com/photo/1?width=40&height=30', body=_png_bytes())

        loaded = image.load_image(width=40, height=30)

    assert loaded is image.image
    assert loaded is not None
    assert loaded.size == (4, 3)


def test_load_image_http_error_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    image = KomootImage(PLAIN_URL)
    with responses.RequestsMock() as mock, caplog.at_level(logging.WARNING, logger='kompy'):
        mock.get(PLAIN_URL, status=404)

        assert image.load_image() is None

    assert image.image is None
    assert 'Could not download image' in caplog.text
    assert caplog.records[0].name == 'kompy.image'


def test_load_image_connection_error_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    image = KomootImage(PLAIN_URL)
    with responses.RequestsMock() as mock, caplog.at_level(logging.WARNING, logger='kompy'):
        mock.get(PLAIN_URL, body=requests.ConnectionError('offline'))

        assert image.load_image() is None

    assert 'offline' in caplog.text


def test_load_image_undecodable_data_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    image = KomootImage(PLAIN_URL)
    with responses.RequestsMock() as mock, caplog.at_level(logging.WARNING, logger='kompy'):
        mock.get(PLAIN_URL, body=b'this is not an image')

        assert image.load_image() is None

    assert 'Could not decode image' in caplog.text


def test_load_image_without_pillow_raises_helpful_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, 'PIL', None)

    with pytest.raises(ImportError, match=r'kompy\[images\]'):
        KomootImage(PLAIN_URL).load_image()


def test_downloaded_image_is_not_part_of_equality_or_repr() -> None:
    image = KomootImage(PLAIN_URL)
    image.image = Image.new('RGB', (1, 1))

    assert image == KomootImage(PLAIN_URL)
    assert 'image=' not in repr(image).replace('image_url=', '')
