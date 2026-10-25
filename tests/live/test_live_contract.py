"""
Live contract tests: check kompy against the real Komoot API.

Run with ``KOMOOT_EMAIL=... KOMOOT_PASSWORD=... pytest -m live`` (add ``KOMOOT_LIVE_WRITE=1`` for the tests that
upload, change and delete a private tour; they always clean up). The suite sends about 40 requests.
"""

from __future__ import annotations

import logging
import random
import uuid
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import gpxpy.gpx
import pytest
from gpxpy.gpx import GPX

from kompy import Coordinate, Highlight, KomootConnector, KomootImage, Tour, User
from kompy.constants import PrivacyStatus, TourTypes
from kompy.exceptions import AuthenticationError, KomootError, NotFoundError, UnsupportedFormatError
from tests.live.conftest import CallLog, require_tours

pytestmark = pytest.mark.live

logger = logging.getLogger(__name__)

KNOWN_HIGHLIGHT_ID = 85124
GARBAGE_TOUR_ID = 999_999_999_999
LIVE_TEST_PREFIX = 'kompy-live-test-'


# ----------------------------------------------------------------- authentication


def test_login_exposes_username_and_token(live_connector: KomootConnector) -> None:
    assert live_connector.username
    assert live_connector.token
    assert live_connector.token not in repr(live_connector)


def test_wrong_password_raises_authentication_error(credentials: tuple[str, str]) -> None:
    with pytest.raises(AuthenticationError) as caught:
        KomootConnector(credentials[0], 'definitely-not-the-password', max_retries=0)
    assert caught.value.status_code in {401, 403}


def test_wrong_token_raises_authentication_error(live_connector: KomootConnector) -> None:
    with pytest.raises(AuthenticationError) as caught:
        KomootConnector.from_token(live_connector.username, 'not-a-token', validate=True, max_retries=0)
    assert caught.value.status_code == 401


# ----------------------------------------------------------------- tour listing


def test_first_page_parses(first_page: list[Tour]) -> None:
    assert all(isinstance(tour.id, int) for tour in first_page)
    assert len({tour.id for tour in first_page}) == len(first_page)
    assert all(tour.status in PrivacyStatus.list_all() for tour in first_page)


def test_pagination_matches_one_big_page(live_connector: KomootConnector) -> None:
    paginated = live_connector.get_tours(limit=150, page_size=50)  # three requests
    one_page = live_connector.get_tours(limit=150, page_size=150)  # one request
    assert [tour.id for tour in paginated] == [tour.id for tour in one_page]
    assert 0 < len(paginated) <= 150


def test_limit_is_a_total_maximum(live_connector: KomootConnector, first_page: list[Tour], call_log: CallLog) -> None:
    require_tours(first_page, 3)
    mark = call_log.mark()
    tours = live_connector.get_tours(limit=3)
    assert len(tours) == 3
    assert len(call_log.since(mark)) == 1


def test_page_returns_that_page(live_connector: KomootConnector, first_page: list[Tour]) -> None:
    require_tours(first_page, 6)
    first_six = live_connector.get_tours(limit=6)
    second_page = live_connector.get_tours(page=1, limit=3)
    assert [tour.id for tour in second_page] == [tour.id for tour in first_six[3:6]]


def test_status_filter_is_applied_locally(live_connector: KomootConnector, first_page: list[Tour]) -> None:
    statuses = Counter(str(tour.status) for tour in first_page)
    rarest = min(statuses, key=lambda status: statuses[status])
    filtered = live_connector.get_tours(limit=5, status=rarest)
    assert filtered
    assert all(tour.status == rarest for tour in filtered)


def test_tour_type_filter(live_connector: KomootConnector) -> None:
    planned = live_connector.get_tours(limit=5, tour_type=TourTypes.TOUR_PLANNED)
    assert all(tour.is_planned for tour in planned)


def test_iter_tours_is_lazy(live_connector: KomootConnector, call_log: CallLog) -> None:
    mark = call_log.mark()
    tours: Iterator[Tour] = live_connector.iter_tours(page_size=2)
    assert call_log.since(mark) == []
    taken = [next(tours) for _ in range(3)]
    assert len(taken) == 3
    assert len(call_log.since(mark)) == 2


# ----------------------------------------------------------------- single tours


def test_recorded_tour_by_id(live_connector: KomootConnector, recorded_tour: Tour) -> None:
    tour = live_connector.get_tour_by_id(recorded_tour.id, embedded=True)
    assert tour.id == recorded_tour.id
    assert tour.is_recorded
    assert tour.coordinates
    assert tour.summary is None


def test_planned_tour_by_id(live_connector: KomootConnector, planned_tour: Tour) -> None:
    tour = live_connector.get_tour_by_id(planned_tour.id, embedded=True)
    assert tour.is_planned
    assert tour.coordinates
    assert tour.way_type_segments
    assert tour.surface_segments
    assert tour.summary is not None


def test_garbage_tour_id_raises_not_found(live_connector: KomootConnector) -> None:
    with pytest.raises(NotFoundError):
        live_connector.get_tour_by_id(GARBAGE_TOUR_ID)


def test_tour_gpx(live_connector: KomootConnector, recorded_tour: Tour) -> None:
    gpx = live_connector.get_tour_gpx(recorded_tour.id)
    assert isinstance(gpx, GPX)
    assert gpx.get_track_points_no() > 0


def test_fit_of_planned_tour(live_connector: KomootConnector, planned_tour: Tour) -> None:
    fit = live_connector.get_tour_fit(planned_tour.id)
    assert fit.records


def test_fit_of_recorded_tour_is_unsupported(live_connector: KomootConnector, recorded_tour: Tour) -> None:
    with pytest.raises(UnsupportedFormatError):
        live_connector.get_tour_fit(recorded_tour.id)


def test_tour_coordinates(live_connector: KomootConnector, recorded_tour: Tour) -> None:
    coordinates = live_connector.get_tour_coordinates(recorded_tour)
    assert coordinates
    assert all(isinstance(coordinate, Coordinate) for coordinate in coordinates)
    assert recorded_tour.coordinates == coordinates


def test_tour_cover_images(live_connector: KomootConnector, recorded_tour: Tour) -> None:
    images = live_connector.get_tour_cover_images(recorded_tour.id)
    assert all(isinstance(image, KomootImage) for image in images)


def test_download_tour(live_connector: KomootConnector, recorded_tour: Tour, tmp_path: Path) -> None:
    path = live_connector.download_tour(recorded_tour, tmp_path, 'gpx')
    assert path.parent == tmp_path
    assert path.name.startswith(f'{recorded_tour.id}')
    assert path.suffix == '.gpx'
    assert path.read_bytes().lstrip().startswith(b'<?xml')
    assert list(tmp_path.iterdir()) == [path]


# ----------------------------------------------------------------- users and highlights


def test_get_user(live_connector: KomootConnector) -> None:
    user = live_connector.get_user()
    assert isinstance(user, User)
    assert user.username == live_connector.username


def test_get_user_highlights(live_connector: KomootConnector) -> None:
    highlights = live_connector.get_user_highlights(limit=3)
    assert len(highlights) <= 3
    assert all(isinstance(highlight, Highlight) for highlight in highlights)


def test_get_highlight(live_connector: KomootConnector) -> None:
    highlight = live_connector.get_highlight(KNOWN_HIGHLIGHT_ID)
    assert highlight.id == KNOWN_HIGHLIGHT_ID
    assert highlight.name


# ----------------------------------------------------------------- writes (KOMOOT_LIVE_WRITE=1)


def _unique_gpx() -> GPX:
    """
    A ~4 km recorded hike with a random start, so Komoot never sees it as a duplicate of an earlier run.

    (``tests/resources/example.gpx`` is too short: Komoot answers HTTP 400 "Failed to import tour" for it.)
    """
    rnd = random.Random()
    lat, lon = 46.5 + rnd.random() / 10, 8.8 + rnd.random() / 10
    start = datetime(2025, 6, 1, 8, tzinfo=UTC) + timedelta(minutes=rnd.randint(0, 500_000))
    gpx = gpxpy.gpx.GPX()
    track = gpxpy.gpx.GPXTrack()
    segment = gpxpy.gpx.GPXTrackSegment()
    gpx.tracks.append(track)
    track.segments.append(segment)
    for i in range(300):
        segment.points.append(
            gpxpy.gpx.GPXTrackPoint(
                lat + i * 1e-4, lon + i * 1e-4, elevation=500 + i / 2, time=start + timedelta(seconds=5 * i)
            )
        )
    return gpx


@pytest.mark.usefixtures('write_enabled')
def test_upload_change_and_delete_tour(live_connector: KomootConnector, call_log: CallLog) -> None:
    name = f'{LIVE_TEST_PREFIX}{uuid.uuid4().hex[:8]}'
    gpx = _unique_gpx()
    created_ids: set[int] = set()
    try:
        mark = call_log.mark()
        upload = live_connector.upload_tour(gpx, 'hike', name, time_in_motion=600, status=PrivacyStatus.PRIVATE)
        created_ids.add(upload.tour_id)
        logger.info('upload: %s created=%s', call_log.since(mark), upload.created)
        assert upload
        assert upload.created
        # Komoot's upload endpoint ignores the status; kompy must apply it right after the upload.
        assert upload.status == PrivacyStatus.PRIVATE

        tour = live_connector.get_tour_by_id(upload.tour_id)
        assert tour.name == name
        assert tour.is_recorded
        assert tour.sport == 'hike'
        assert tour.time_in_motion == 600
        assert tour.status == PrivacyStatus.PRIVATE  # the privacy status requested at upload is the one it has

        # Komoot recognises an identical file and answers 202 with the id of the existing tour, unchanged.
        mark = call_log.mark()
        duplicate = live_connector.upload_tour(gpx, 'hike', f'{name}-dup', status=PrivacyStatus.PRIVATE)
        created_ids.add(duplicate.tour_id)
        logger.info('duplicate upload: %s created=%s', call_log.since(mark), duplicate.created)
        assert duplicate.created is False
        assert duplicate.tour_id == upload.tour_id

        renamed = f'{name}-renamed'
        mark = call_log.mark()
        assert live_connector.change_tour(upload.tour_id, tour_name=renamed, status=PrivacyStatus.FRIENDS) is True
        logger.info('change: %s', call_log.since(mark))
        changed = live_connector.get_tour_by_id(upload.tour_id)
        assert changed.name == renamed
        assert changed.status == PrivacyStatus.FRIENDS

        assert live_connector.change_tour(upload.tour_id, status=PrivacyStatus.PRIVATE) is True
        assert live_connector.get_tour_by_id(upload.tour_id).status == PrivacyStatus.PRIVATE
    finally:
        cleanup_errors: list[tuple[int, KomootError]] = []
        for tour_id in created_ids:  # try every id, even when one delete fails
            mark = call_log.mark()
            try:
                live_connector.delete_tour(tour_id)
            except KomootError as error:
                cleanup_errors.append((tour_id, error))
            logger.info('delete %s: %s', tour_id, call_log.since(mark))
        if cleanup_errors:
            pytest.fail(f'Cleanup failed, delete these tours by hand: {cleanup_errors}')
    for tour_id in created_ids:
        mark = call_log.mark()
        with pytest.raises(NotFoundError):
            live_connector.get_tour_by_id(tour_id)
        logger.info('get after delete %s: %s', tour_id, call_log.since(mark))


@pytest.mark.usefixtures('write_enabled')
def test_plan_tour(live_connector: KomootConnector, call_log: CallLog) -> None:
    name = f'{LIVE_TEST_PREFIX}{uuid.uuid4().hex[:8]}'
    start = (53.14, 8.21)
    mark = call_log.mark()
    tour = live_connector.plan_tour([start, (53.08, 8.31), start], name, 'hike', status=PrivacyStatus.PRIVATE)
    logger.info('plan: %s', call_log.since(mark))
    try:
        assert tour.is_planned
        fetched = live_connector.get_tour_by_id(tour.id)
        assert fetched.name == name
        assert fetched.is_planned
        assert fetched.sport == 'hike'
        assert fetched.status == PrivacyStatus.PRIVATE  # unlike uploads, saving a planned tour keeps the status
        assert fetched.distance > 1000
        assert live_connector.get_tour_fit(tour.id)  # planned tours can be exported as FIT
    finally:
        live_connector.delete_tour(tour.id)


@pytest.mark.usefixtures('write_enabled')
def test_no_live_test_tours_left(live_connector: KomootConnector) -> None:
    listed = live_connector.get_tours(tour_name=LIVE_TEST_PREFIX)
    # Never trust the server-side name filter alone before deleting anything.
    leftovers = [tour for tour in listed if (tour.name or '').startswith(LIVE_TEST_PREFIX)]
    for tour in leftovers:
        live_connector.delete_tour(tour.id)
    assert [tour.name for tour in leftovers] == []
