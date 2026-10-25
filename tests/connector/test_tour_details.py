"""Single tours: details, GPX/FIT exports, coordinates, cover images and downloads."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import responses
from fit_tool.fit_file import FitFile
from gpxpy.gpx import GPX

from kompy import KomootConnector, Tour
from kompy.constants import TourObjectTypes, TourTypes
from kompy.exceptions import (
    DownloadError,
    KomootAPIError,
    KomootResponseError,
    NotFoundError,
    ServerError,
    UnsupportedFormatError,
)
from kompy.komoot_connector import DEFAULT_EMBEDDED, tour_filename
from tests.conftest import API, EXAMPLE_GPX, USERNAME, make_tour, query_of, read_api_fixture, tour_page
from tests.connector._fit import fit_bytes

TOUR_ID = 1000000002
TOUR_URL = f'{API}/tours/{TOUR_ID}'
GPX_BYTES = EXAMPLE_GPX.read_bytes()


# ----------------------------------------------------------------- get_tour_by_id


def test_get_tour_by_id(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOUR_URL, json=read_api_fixture('tour_planned_by_id'))

    tour = connector.get_tour_by_id(TOUR_ID)

    assert isinstance(tour, Tour)
    assert tour.id == TOUR_ID
    request = mocked_responses.calls[1].request
    assert query_of(request) == {}  # no bogus "Type" query parameter
    assert request.headers['Accept'] == 'application/hal+json, application/json'


@pytest.mark.parametrize('object_type', [None, '', 'kompy', TourObjectTypes.KOMPY])
def test_get_tour_by_id_kompy_object_types(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, object_type: str | None
) -> None:
    mocked_responses.get(TOUR_URL, json=read_api_fixture('tour_planned_by_id'))

    assert isinstance(connector.get_tour_by_id(str(TOUR_ID), None, object_type), Tour)


def test_share_token_is_sent(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOUR_URL, json=read_api_fixture('tour_planned_by_id'))

    connector.get_tour_by_id(TOUR_ID, share_token='s3cr3t')

    assert query_of(mocked_responses.calls[1].request) == {'share_token': ['s3cr3t']}


def test_embedded_true(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOUR_URL, json=read_api_fixture('tour_planned_by_id_embedded'))

    tour = connector.get_tour_by_id(TOUR_ID, embedded=True)

    assert query_of(mocked_responses.calls[1].request) == {
        '_embedded': [','.join(DEFAULT_EMBEDDED)],
        'directions': ['v2'],
    }
    assert tour.coordinates  # filled from _embedded.coordinates


@pytest.mark.parametrize(
    ('embedded', 'expected'),
    [('timeline', {'_embedded': ['timeline']}), (['coordinates', 'surfaces'], {'_embedded': ['coordinates,surfaces']})],
)
def test_embedded_selection(
    connector: KomootConnector,
    mocked_responses: responses.RequestsMock,
    embedded: str | list[str],
    expected: dict[str, list[str]],
) -> None:
    mocked_responses.get(TOUR_URL, json=read_api_fixture('tour_planned_by_id'))

    connector.get_tour_by_id(TOUR_ID, embedded=embedded)

    assert query_of(mocked_responses.calls[1].request) == expected


def test_tour_not_found(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{API}/tours/garbage', status=404)

    with pytest.raises(NotFoundError) as caught:
        connector.get_tour_by_id('garbage')

    assert isinstance(caught.value, ValueError)  # what older kompy versions raised


def test_unparseable_tour(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(TOUR_URL, json={'name': 'no id'})

    with pytest.raises(KomootResponseError, match=f'tour {TOUR_ID} could not be parsed'):
        connector.get_tour_by_id(TOUR_ID)


def test_invalid_object_type(connector: KomootConnector) -> None:
    with pytest.raises(ValueError, match='Invalid object type'):
        connector.get_tour_by_id(TOUR_ID, object_type='kml')


def test_embedded_with_file_format_is_rejected(connector: KomootConnector) -> None:
    with pytest.raises(ValueError, match='embedded'):
        connector.get_tour_by_id(TOUR_ID, object_type='gpx', embedded=True)


# ----------------------------------------------------------------- GPX


@pytest.mark.parametrize('object_type', ['gpx', TourObjectTypes.GPX])
def test_get_tour_by_id_gpx(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, object_type: str
) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', body=GPX_BYTES, content_type='application/gpx+xml')

    gpx = connector.get_tour_by_id(TOUR_ID, None, object_type)

    assert isinstance(gpx, GPX)
    assert gpx.tracks[0].name == 'Example gpx'
    assert mocked_responses.calls[1].request.headers['Accept'] == 'application/gpx+xml'


def test_get_tour_gpx_stores_track_on_tour(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    tour = Tour(read_api_fixture('tour_recorded_by_id'))
    mocked_responses.get(f'{API}/tours/{tour.id}.gpx', body=GPX_BYTES)

    gpx = connector.get_tour_gpx(tour, share_token='tok')

    assert tour.gpx_track is gpx
    assert query_of(mocked_responses.calls[1].request) == {'share_token': ['tok']}


@pytest.mark.parametrize('body', [b'<not-gpx', b'\xff\xfe\x00garbage'])
def test_invalid_gpx(connector: KomootConnector, mocked_responses: responses.RequestsMock, body: bytes) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', body=body)

    with pytest.raises(KomootResponseError, match='GPX track'):
        connector.get_tour_gpx(TOUR_ID)


def test_empty_gpx(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', body=b'')

    with pytest.raises(KomootResponseError, match='empty'):
        connector.get_tour_gpx(TOUR_ID)


# ----------------------------------------------------------------- FIT


@pytest.mark.parametrize('object_type', ['fit', TourObjectTypes.FIT])
def test_get_tour_by_id_fit(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, object_type: str
) -> None:
    mocked_responses.get(f'{TOUR_URL}.fit', body=fit_bytes(), content_type='application/vnd.ant.fit')

    fit = connector.get_tour_by_id(TOUR_ID, object_type=object_type)

    assert isinstance(fit, FitFile)
    assert mocked_responses.calls[1].request.headers['Accept'] == 'application/vnd.ant.fit'


def test_fit_of_recorded_tour_is_unsupported(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(f'{API}/tours/1000000001.fit', status=400, body=b'')  # the real answer: 400, empty body

    with pytest.raises(UnsupportedFormatError, match='only provides FIT files for planned tours') as caught:
        connector.get_tour_fit(1000000001)

    assert isinstance(caught.value, ValueError)
    assert isinstance(caught.value.__cause__, KomootAPIError)


def test_fit_server_error_is_not_masked(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{TOUR_URL}.fit', status=500)

    with pytest.raises(ServerError):
        connector.get_tour_fit(TOUR_ID)


def test_gpx_400_is_not_reported_as_unsupported_format(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', status=400)

    with pytest.raises(KomootAPIError) as caught:
        connector.get_tour_gpx(TOUR_ID)

    assert not isinstance(caught.value, UnsupportedFormatError)


def test_invalid_fit(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{TOUR_URL}.fit', body=b'garbage')

    with pytest.raises(KomootResponseError, match='FIT file'):
        connector.get_tour_fit(TOUR_ID)


# ----------------------------------------------------------------- coordinates and cover images


def test_get_tour_coordinates(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    payload = read_api_fixture('tour_coordinates')
    payload['items'].append({'lat': 'broken'})
    mocked_responses.get(f'{TOUR_URL}/coordinates', json=payload)

    coordinates = connector.get_tour_coordinates(TOUR_ID)

    assert len(coordinates) == 3  # the malformed entry is skipped
    assert (coordinates[1].lat, coordinates[1].lon, coordinates[1].alt, coordinates[1].time) == (
        46.002188,
        8.004596,
        578.4,
        2000.0,
    )


def test_get_tour_coordinates_stores_them_on_tour(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    tour = Tour(read_api_fixture('tour_recorded_by_id'))
    mocked_responses.get(f'{API}/tours/{tour.id}/coordinates', json=read_api_fixture('tour_coordinates'))

    coordinates = connector.get_tour_coordinates(tour)

    assert tour.coordinates == coordinates


def test_get_tour_coordinates_unexpected_payload(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(f'{TOUR_URL}/coordinates', json={'oops': []})

    with pytest.raises(KomootResponseError, match='items'):
        connector.get_tour_coordinates(TOUR_ID)


def test_get_tour_cover_images_empty(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(f'{TOUR_URL}/cover_images/', json=read_api_fixture('tour_cover_images'))

    assert connector.get_tour_cover_images(TOUR_ID) == []


def test_get_tour_cover_images_paginated(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    image = {'src': 'https://img/{width}?w={width}', 'templated': True, 'type': 'image/*'}
    mocked_responses.get(
        f'{TOUR_URL}/cover_images/',
        json={'_embedded': {'items': [image, {'no': 'src'}]}, 'page': {'number': 0, 'totalPages': 2}},
    )
    mocked_responses.get(
        f'{TOUR_URL}/cover_images/',
        json={'_embedded': {'items': [{'src': 'https://img/2'}]}, 'page': {'number': 1, 'totalPages': 2}},
    )

    images = connector.get_tour_cover_images(TOUR_ID)

    assert [img.image_url for img in images] == ['https://img/{width}?w={width}', 'https://img/2']
    assert images[0].templated is True


# ----------------------------------------------------------------- downloads


def test_download_tour_to_file(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', body=GPX_BYTES)
    target = tmp_path / 'nested' / 'tour.gpx'

    path = connector.download_tour(TOUR_ID, target)

    assert path == target
    assert target.read_bytes() == GPX_BYTES  # raw bytes, untouched
    assert list(target.parent.iterdir()) == [target]  # no leftover temporary file


def test_download_tour_to_directory(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(f'{TOUR_URL}.fit', body=fit_bytes())
    mocked_responses.get(f'{TOUR_URL}.gpx', body=GPX_BYTES)
    tour = Tour(read_api_fixture('tour_planned_by_id'))

    fit_path = connector.download_tour(TOUR_ID, tmp_path, fmt='fit')
    gpx_path = connector.download_tour(tour, tmp_path)

    assert fit_path == tmp_path / f'{TOUR_ID}.fit'
    assert gpx_path == tmp_path / f'{TOUR_ID}_sample-name.gpx'
    assert fit_path.read_bytes() == fit_bytes()


@pytest.mark.parametrize('separator', ['/', os.sep])
def test_download_tour_to_new_directory_with_trailing_separator(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path, separator: str
) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', body=GPX_BYTES)
    directory = tmp_path / 'backup'

    path = connector.download_tour(TOUR_ID, f'{directory}{separator}')

    assert path == directory / f'{TOUR_ID}.gpx'  # not a file named "backup"
    assert directory.is_dir()
    assert path.read_bytes() == GPX_BYTES


def test_download_tour_failed_write_leaves_no_partial_file(
    connector: KomootConnector,
    mocked_responses: responses.RequestsMock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', body=GPX_BYTES)
    target = tmp_path / 'tour.gpx'
    target.write_bytes(b'previous')

    def fail(*_args: object) -> None:
        raise OSError('disk full')

    monkeypatch.setattr('kompy.komoot_connector.os.replace', fail)

    with pytest.raises(OSError, match='disk full'):
        connector.download_tour(TOUR_ID, target)

    assert list(tmp_path.iterdir()) == [target]  # the temporary file was removed
    assert target.read_bytes() == b'previous'  # and the existing file was not truncated


@pytest.mark.skipif(os.name != 'posix', reason='POSIX file modes')
def test_download_tour_file_mode_follows_umask(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(f'{TOUR_URL}.gpx', body=GPX_BYTES)
    previous_umask = os.umask(0o022)
    try:
        path = connector.download_tour(TOUR_ID, tmp_path / 'tour.gpx')
    finally:
        os.umask(previous_umask)

    assert path.stat().st_mode & 0o777 == 0o644  # not the 0o600 of a tempfile.mkstemp file


def test_download_tour_invalid_format(connector: KomootConnector, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='Unsupported format'):
        connector.download_tour(TOUR_ID, tmp_path, fmt='kml')  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('Über den Säntis!', '42_uber-den-santis.gpx'),
        ('  ', '42.gpx'),
        ('日本', '42.gpx'),
        (None, '42.gpx'),
        ('a' * 200, f'42_{"a" * 80}.gpx'),
        ('../../etc/passwd', '42_etc-passwd.gpx'),
    ],
)
def test_tour_filename(name: str | None, expected: str) -> None:
    assert tour_filename(Tour({'id': 42, 'name': name}), 'gpx') == expected


def test_download_tours(connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path) -> None:
    tours = [make_tour(1, name='First'), make_tour(2, name='Second'), make_tour(3, name='Third')]
    mocked_responses.get(f'{API}/users/{USERNAME}/tours/', json=tour_page(tours))
    (tmp_path / '2_second.gpx').write_bytes(b'existing')
    mocked_responses.get(f'{API}/tours/1.gpx', body=GPX_BYTES)
    mocked_responses.get(f'{API}/tours/3.gpx', body=GPX_BYTES)

    paths = connector.download_tours(tmp_path, tour_type=TourTypes.TOUR_RECORDED)

    assert paths == [tmp_path / '1_first.gpx', tmp_path / '2_second.gpx', tmp_path / '3_third.gpx']
    assert (tmp_path / '2_second.gpx').read_bytes() == b'existing'  # skipped, not overwritten
    assert query_of(mocked_responses.calls[1].request)['type'] == ['tour_recorded']


def test_download_tours_skips_a_tour_downloaded_under_its_id_only(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(f'{API}/users/{USERNAME}/tours/', json=tour_page([make_tour(1, name='First')]))
    (tmp_path / '1.gpx').write_bytes(b'by id')
    (tmp_path / '12_other.gpx').write_bytes(b'another tour')

    assert connector.download_tours(tmp_path) == [tmp_path / '1.gpx']
    assert not (tmp_path / '1_first.gpx').exists()


def test_download_tours_overwrite(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(f'{API}/users/{USERNAME}/tours/', json=tour_page([make_tour(1, name='First')]))
    mocked_responses.get(f'{API}/tours/1.gpx', body=GPX_BYTES)
    (tmp_path / '1_first.gpx').write_bytes(b'old')

    connector.download_tours(tmp_path / '.', overwrite=True)

    assert (tmp_path / '1_first.gpx').read_bytes() == GPX_BYTES


def test_download_tours_collects_failures(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    tours = [make_tour(1, name='Recorded'), make_tour(2, name='Planned')]
    mocked_responses.get(f'{API}/users/{USERNAME}/tours/', json=tour_page(tours))
    mocked_responses.get(f'{API}/tours/1.fit', status=400)
    mocked_responses.get(f'{API}/tours/2.fit', body=fit_bytes())
    destination = tmp_path / 'backup'

    with pytest.raises(DownloadError, match=r'1 tour\(s\) could not be downloaded: 1\.') as caught:
        connector.download_tours(destination, fmt='fit', limit=2)

    assert caught.value.paths == [destination / '2_planned.fit']
    assert isinstance(caught.value.failures[1], UnsupportedFormatError)
    assert (destination / '2_planned.fit').exists()
    assert not (destination / '1_recorded.fit').exists()


def test_download_tours_invalid_format(connector: KomootConnector, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match='Unsupported format'):
        connector.download_tours(tmp_path, fmt='tcx')  # type: ignore[arg-type]
