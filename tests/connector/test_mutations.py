"""Changing tours: upload, change and delete."""

from __future__ import annotations

import logging
from pathlib import Path

import gpxpy
import pytest
import responses
from fit_tool.fit_file import FitFile

from kompy import KomootConnector, Tour, UploadResult
from kompy.constants import PrivacyStatus, SupportedActivities
from kompy.exceptions import (
    AuthenticationError,
    KomootAPIError,
    KomootResponseError,
    NotFoundError,
    ServerError,
    UploadStatusError,
)
from tests.conftest import API, EXAMPLE_GPX, json_body, query_of
from tests.connector._fit import fit_bytes

UPLOAD_URL = f'{API}/tours/'
TOUR_URL = f'{API}/tours/42'


@pytest.fixture
def gpx() -> gpxpy.gpx.GPX:
    return gpxpy.parse(EXAMPLE_GPX.read_text(encoding='utf-8'))


# ----------------------------------------------------------------- upload


def test_upload_gpx_object(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42, 'name': 'Example gpx', 'status': 'private'})

    result = connector.upload_tour(gpx, SupportedActivities.HIKING, 'Example gpx', 3600, PrivacyStatus.PRIVATE)

    assert result == UploadResult(tour_id=42, created=True)
    assert result.raw == {'id': 42, 'name': 'Example gpx', 'status': 'private'}
    assert result.status == 'private'
    assert len(mocked_responses.calls) == 2  # Komoot applied the status: no follow-up PATCH
    request = mocked_responses.calls[1].request
    assert query_of(request) == {
        'data_type': ['gpx'],  # once, not twice
        'sport': ['hike'],
        'name': ['Example gpx'],
        'status': ['private'],
        'time_in_motion': ['3600'],
    }
    assert request.headers['Content-Type'] == 'application/octet-stream'
    assert request.headers['User-Agent'].startswith('kompy/')
    assert request.body == gpx.to_xml().encode('utf-8')


def test_upload_defaults(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': '42', 'status': 'friends'})

    connector.upload_tour(gpx, 'hike', 'Walk')

    query = query_of(mocked_responses.calls[1].request)
    assert query['status'] == ['friends']
    assert 'time_in_motion' not in query  # no "time_in_motion=None"


def test_upload_without_status(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42})

    connector.upload_tour(gpx, 'hike', 'Walk', status=None)

    assert 'status' not in query_of(mocked_responses.calls[1].request)


def test_upload_duplicate_returns_existing_id(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=202, json={'id': 7})

    result = connector.upload_tour(gpx, 'hike', 'Walk')

    assert result.tour_id == 7
    assert result.created is False
    assert result  # truthy, like the True older versions returned


def test_upload_fit_object(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, caplog: pytest.LogCaptureFixture
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 43, 'status': 'friends'})
    fit = FitFile.from_bytes(fit_bytes())

    with caplog.at_level(logging.WARNING, logger='kompy'):
        result = connector.upload_tour(fit, 'racebike', 'Ride', time_in_motion=100)

    assert result.tour_id == 43
    request = mocked_responses.calls[1].request
    assert query_of(request)['data_type'] == ['fit']
    assert 'time_in_motion' not in query_of(request)
    assert request.body == bytes(fit.to_bytes())
    assert 'time_in_motion is ignored' in caplog.text


@pytest.mark.parametrize(('suffix', 'data_type'), [('.gpx', 'gpx'), ('.GPX', 'gpx'), ('.fit', 'fit'), ('.tcx', 'tcx')])
def test_upload_from_path(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, tmp_path: Path, suffix: str, data_type: str
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 44, 'status': 'friends'})
    path = tmp_path / f'tour{suffix}'
    path.write_bytes(b'file-content')

    connector.upload_tour(path, 'hike', 'From file')

    request = mocked_responses.calls[1].request
    assert query_of(request)['data_type'] == [data_type]
    assert request.body == b'file-content'


def test_upload_from_string_path(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 45, 'status': 'friends'})

    assert connector.upload_tour(str(EXAMPLE_GPX), 'hike', 'Example').tour_id == 45
    assert mocked_responses.calls[1].request.body == EXAMPLE_GPX.read_bytes()


def test_upload_unsupported_file(connector: KomootConnector, tmp_path: Path) -> None:
    path = tmp_path / 'tour.kml'
    path.write_text('<kml/>')

    with pytest.raises(ValueError, match=r'\.gpx, \.fit or \.tcx'):
        connector.upload_tour(path, 'hike', 'x')


def test_upload_missing_file(connector: KomootConnector, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        connector.upload_tour(tmp_path / 'missing.gpx', 'hike', 'x')


def test_upload_invalid_object(connector: KomootConnector) -> None:
    with pytest.raises(TypeError, match='GPX object, a FitFile or a file path'):
        connector.upload_tour(b'raw bytes', 'hike', 'x')


def test_upload_invalid_status(connector: KomootConnector, gpx: gpxpy.gpx.GPX) -> None:
    with pytest.raises(ValueError, match='Invalid status'):
        connector.upload_tour(gpx, 'hike', 'x', status='everyone')


def test_upload_negative_time_in_motion(connector: KomootConnector, gpx: gpxpy.gpx.GPX) -> None:
    with pytest.raises(ValueError, match='time_in_motion'):
        connector.upload_tour(gpx, 'hike', 'x', time_in_motion=-1)


def test_upload_unknown_sport_warns(
    connector: KomootConnector,
    mocked_responses: responses.RequestsMock,
    gpx: gpxpy.gpx.GPX,
    caplog: pytest.LogCaptureFixture,
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 1, 'status': 'friends'})

    with caplog.at_level(logging.WARNING, logger='kompy'):
        connector.upload_tour(gpx, 'padel', 'x')

    assert query_of(mocked_responses.calls[1].request)['sport'] == ['padel']
    assert "Unknown sport 'padel'" in caplog.text


@pytest.mark.parametrize(
    ('status', 'exception'), [(400, KomootAPIError), (401, AuthenticationError), (500, ServerError)]
)
def test_upload_failure_raises(
    connector: KomootConnector,
    mocked_responses: responses.RequestsMock,
    gpx: gpxpy.gpx.GPX,
    status: int,
    exception: type[KomootAPIError],
) -> None:
    mocked_responses.post(UPLOAD_URL, status=status, json={'message': 'File unreadable'})

    with pytest.raises(exception):
        connector.upload_tour(gpx, 'hike', 'x')


@pytest.mark.parametrize('body', [{'name': 'no id'}, {'id': 'abc'}, {'id': None}])
def test_upload_response_without_id(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX, body: dict[str, object]
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json=body)

    with pytest.raises(KomootResponseError, match='tour id'):
        connector.upload_tour(gpx, 'hike', 'x')


# ----------------------------------------------------------------- upload: visibility
# Komoot's upload endpoint ignores the status parameter (verified live: a tour uploaded with status=private came
# back as friends), so kompy sets the requested visibility with a PATCH right after the upload.


def test_upload_applies_ignored_status_with_a_patch(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42, 'status': 'friends'})
    mocked_responses.patch(TOUR_URL, json={'id': 42, 'status': 'private'})

    result = connector.upload_tour(gpx, 'hike', 'Walk', status=PrivacyStatus.PRIVATE)

    patch = mocked_responses.calls[2].request
    assert patch.method == 'PATCH'
    assert json_body(patch) == {'status': 'private'}
    assert result.tour_id == 42
    assert result.created is True
    assert result.status == 'private'
    assert result.raw['status'] == 'private'


def test_upload_patches_when_the_response_has_no_status(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42})
    mocked_responses.patch(TOUR_URL, status=204)

    assert connector.upload_tour(gpx, 'hike', 'Walk').status == 'friends'
    assert json_body(mocked_responses.calls[2].request) == {'status': 'friends'}


def test_upload_without_status_keeps_the_account_default(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42, 'status': 'public'})

    result = connector.upload_tour(gpx, 'hike', 'Walk', status=None)

    assert result.status == 'public'
    assert len(mocked_responses.calls) == 2  # no PATCH


def test_upload_duplicate_leaves_the_existing_tour_alone(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=202, json={'id': 7, 'status': 'public'})

    result = connector.upload_tour(gpx, 'hike', 'Walk', status=PrivacyStatus.PRIVATE)

    assert result.created is False
    assert result.status == 'public'  # reported truthfully, not changed
    assert len(mocked_responses.calls) == 2


def test_upload_status_patch_failure_names_the_tour(
    connector: KomootConnector, mocked_responses: responses.RequestsMock, gpx: gpxpy.gpx.GPX
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42, 'status': 'friends'})
    mocked_responses.patch(TOUR_URL, status=500)

    with pytest.raises(UploadStatusError, match='Tour 42 was uploaded with visibility friends') as caught:
        connector.upload_tour(gpx, 'hike', 'Walk', status=PrivacyStatus.PRIVATE)

    assert caught.value.tour_id == 42
    assert caught.value.requested_status == 'private'
    assert caught.value.actual_status == 'friends'
    assert isinstance(caught.value.__cause__, ServerError)


def test_upload_result_status_ignores_non_strings() -> None:
    assert UploadResult(tour_id=1, created=True, raw={'status': 3}).status is None


# ----------------------------------------------------------------- change


def test_change_tour_sends_only_given_fields(
    connector: KomootConnector, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.patch(TOUR_URL, json={'id': 42})

    assert connector.change_tour(42, status=PrivacyStatus.PRIVATE) is True

    request = mocked_responses.calls[1].request
    assert json_body(request) == {'status': 'private'}  # no JSON nulls for the other fields
    assert request.headers['Content-Type'] == 'application/json'


def test_change_tour_all_fields(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.patch(TOUR_URL, status=204)

    connector.change_tour('42', SupportedActivities.MOUNTAIN_BIKING, 'New name', 'public')

    assert json_body(mocked_responses.calls[1].request) == {
        'sport': 'mtb',
        'name': 'New name',
        'status': 'public',
    }


def test_change_tour_nothing_to_change(connector: KomootConnector) -> None:
    with pytest.raises(ValueError, match='Nothing to change'):
        connector.change_tour(42)


def test_change_tour_invalid_status(connector: KomootConnector) -> None:
    with pytest.raises(ValueError, match='Invalid status'):
        connector.change_tour(42, status='hidden')


def test_change_tour_failure(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.patch(TOUR_URL, status=404)

    with pytest.raises(NotFoundError):
        connector.change_tour(42, tour_name='x')


# ----------------------------------------------------------------- delete


@pytest.mark.parametrize('status', [200, 204])
def test_delete_tour(connector: KomootConnector, mocked_responses: responses.RequestsMock, status: int) -> None:
    mocked_responses.delete(TOUR_URL, status=status)

    assert connector.delete_tour(42) is True
    assert mocked_responses.calls[1].request.method == 'DELETE'


def test_delete_tour_failure(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.delete(TOUR_URL, status=403)

    with pytest.raises(AuthenticationError):
        connector.delete_tour(42)


# ----------------------------------------------------------------- a Tour instead of an id


def test_change_and_delete_accept_a_tour(connector: KomootConnector, mocked_responses: responses.RequestsMock) -> None:
    tour = Tour({'id': 42, 'name': 'Sample name'})
    mocked_responses.patch(TOUR_URL, json={'id': 42})
    mocked_responses.delete(TOUR_URL, status=204)

    assert connector.change_tour(tour, tour_name='x') is True
    assert connector.delete_tour(tour) is True
    assert [call.request.url for call in mocked_responses.calls[1:]] == [TOUR_URL, TOUR_URL]
