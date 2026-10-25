"""
Run the scripts in ``examples/`` against a mocked Komoot API, so they cannot silently rot.

Each example is loaded from its file and its ``main(argv)`` is called with credentials in the environment, the
way a user would run it.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import responses

from tests.conftest import (
    API,
    EMAIL,
    EXAMPLE_GPX,
    PASSWORD,
    USERNAME,
    make_tour,
    query_of,
    read_api_fixture,
    register_login,
    tour_page,
)

EXAMPLES = Path(__file__).parent.parent / 'examples'

# The example scripts ship in the sdist; skip (rather than fail) if a repackaged source tree left them out.
pytestmark = pytest.mark.skipif(not EXAMPLES.is_dir(), reason='examples/ is not available')
TOURS_URL = f'{API}/users/{USERNAME}/tours/'

Main = Callable[[list[str]], int]


@pytest.fixture
def load_example(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Main]:
    """Return a loader that imports an example script by file name (without ``.py``) and returns its ``main``."""

    def load(name: str) -> Main:
        spec = importlib.util.spec_from_file_location(f'kompy_example_{name}', EXAMPLES / f'{name}.py')
        assert spec is not None
        assert spec.loader is not None
        module: ModuleType = importlib.util.module_from_spec(spec)
        # Registered for the duration of the test, as an import would: dataclasses look their module up there.
        monkeypatch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
        main: Main = module.main
        return main

    return load


@pytest.fixture(autouse=True)
def _environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide email/password credentials and keep the examples from configuring the test process' logging."""
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', PASSWORD)
    monkeypatch.delenv('KOMOOT_USERNAME', raising=False)
    monkeypatch.delenv('KOMOOT_TOKEN', raising=False)
    monkeypatch.setattr(logging, 'basicConfig', lambda **_kwargs: None)


@pytest.fixture
def api(mocked_responses: responses.RequestsMock) -> responses.RequestsMock:
    """The mocked API with a successful login registered."""
    register_login(mocked_responses)
    return mocked_responses


def tours(*changes: dict[str, Any]) -> list[dict[str, Any]]:
    """Build listed tour payloads with ids 1, 2, ... and the given field changes."""
    return [make_tour(index, **change) for index, change in enumerate(changes, start=1)]


# ----------------------------------------------------------------- quickstart.py


def test_quickstart(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    detailed = read_api_fixture('tour_planned_by_id_embedded')
    api.get(f'{API}/users/{USERNAME}/', json=read_api_fixture('user'))
    api.get(TOURS_URL, json=tour_page(tours({'name': 'Latest run'}, {'name': 'Older run'})))
    api.get(f'{API}/tours/1', json=detailed)

    assert load_example('quickstart')(['--limit', '2']) == 0

    output = capsys.readouterr().out
    assert 'Logged in as Sample display_name (username 1234567890)' in output
    assert 'Latest run' in output
    assert 'Older run' in output
    assert f'track points:   {len(detailed["_embedded"]["coordinates"]["items"])}' in output
    list_query = query_of(api.calls[2].request)
    assert list_query['limit'] == ['2']
    assert list_query['sort_field'] == ['date']
    assert list_query['sort_direction'] == ['desc']
    assert '_embedded' in query_of(api.calls[3].request)


def test_quickstart_without_tours(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    api.get(f'{API}/users/{USERNAME}/', json=read_api_fixture('user'))
    api.get(TOURS_URL, json=tour_page([], total_pages=0))

    assert load_example('quickstart')([]) == 0

    assert 'No tours yet.' in capsys.readouterr().out


def test_quickstart_reports_api_errors(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    api.get(f'{API}/users/{USERNAME}/', status=404, json={'message': 'Not found'})

    assert load_example('quickstart')([]) == 1

    assert 'Komoot request failed' in capsys.readouterr().out


# ----------------------------------------------------------------- export_all_tours.py


def test_export_all_tours(
    load_example: Callable[[str], Main], api: responses.RequestsMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    gpx = EXAMPLE_GPX.read_bytes()
    api.get(TOURS_URL, json=tour_page(tours({'name': 'Morning run'}, {'name': 'Evening run'})))
    api.get(f'{API}/tours/1.gpx', body=gpx)
    api.get(f'{API}/tours/2.gpx', body=gpx)

    assert load_example('export_all_tours')([str(tmp_path), '--since', '2024-01-01', '--recorded-only']) == 0

    assert sorted(path.name for path in tmp_path.iterdir()) == ['1_morning-run.gpx', '2_evening-run.gpx']
    assert '2 tours saved' in capsys.readouterr().out
    list_query = query_of(api.calls[1].request)
    assert list_query['type'] == ['tour_recorded']
    assert list_query['start_date'] == ['2024-01-01T00:00:00.000Z']


def test_export_fit_only_lists_planned_tours(
    load_example: Callable[[str], Main], api: responses.RequestsMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api.get(TOURS_URL, json=tour_page([]))

    assert load_example('export_all_tours')([str(tmp_path), '--format', 'fit']) == 0

    assert query_of(api.calls[1].request)['type'] == ['tour_planned']
    assert '0 tours saved' in capsys.readouterr().out


def test_export_rejects_recorded_fit(load_example: Callable[[str], Main], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        load_example('export_all_tours')(['backup', '--recorded-only', '--format', 'fit'])

    assert exit_info.value.code == 2
    assert 'cannot be combined' in capsys.readouterr().err


def test_export_reports_failed_tours(
    load_example: Callable[[str], Main], api: responses.RequestsMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api.get(TOURS_URL, json=tour_page(tours({'name': 'Kept'}, {'name': 'Gone'})))
    api.get(f'{API}/tours/1.gpx', body=EXAMPLE_GPX.read_bytes())
    api.get(f'{API}/tours/2.gpx', status=404, json={'message': 'Not found'})

    assert load_example('export_all_tours')([str(tmp_path)]) == 1

    output = capsys.readouterr().out
    assert '1 tours saved' in output
    assert '1 failed' in output
    assert 'tour 2:' in output
    assert [path.name for path in tmp_path.iterdir()] == ['1_kept.gpx']


def test_export_reports_api_errors(
    load_example: Callable[[str], Main], api: responses.RequestsMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    api.get(TOURS_URL, status=403, json={'message': 'Forbidden'})

    assert load_example('export_all_tours')([str(tmp_path)]) == 1

    assert 'Komoot request failed' in capsys.readouterr().out


# ----------------------------------------------------------------- upload_activity.py


def test_upload_activity(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    api.post(f'{API}/tours/', status=201, json={'id': 42, 'status': 'private'})

    assert load_example('upload_activity')([str(EXAMPLE_GPX), '--sport', 'jogging', '--name', 'Morning run']) == 0

    assert 'Uploaded: https://www.komoot.com/tour/42' in capsys.readouterr().out
    query = query_of(api.calls[1].request)
    assert query == {'data_type': ['gpx'], 'sport': ['jogging'], 'name': ['Morning run'], 'status': ['private']}


def test_upload_activity_duplicate(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    api.post(f'{API}/tours/', status=202, json={'id': 7})

    assert load_example('upload_activity')([str(EXAMPLE_GPX), '--status', 'friends']) == 0

    assert 'already had this activity: https://www.komoot.com/tour/7' in capsys.readouterr().out
    query = query_of(api.calls[1].request)
    assert query['name'] == ['example']  # the file name
    assert query['status'] == ['friends']


def test_upload_activity_rejected(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    api.post(f'{API}/tours/', status=400, json={'message': 'Invalid file'})

    assert load_example('upload_activity')([str(EXAMPLE_GPX)]) == 1

    output = capsys.readouterr().out
    assert 'Komoot rejected the upload' in output
    assert 'Invalid file' in output


def test_upload_activity_dry_run_sends_nothing(
    load_example: Callable[[str], Main], mocked_responses: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    assert load_example('upload_activity')([str(EXAMPLE_GPX), '--dry-run']) == 0

    assert 'Would upload' in capsys.readouterr().out
    assert len(mocked_responses.calls) == 0


def test_upload_activity_rejects_missing_file(load_example: Callable[[str], Main], tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exit_info:
        load_example('upload_activity')([str(tmp_path / 'missing.gpx')])

    assert exit_info.value.code == 2


# ----------------------------------------------------------------- stats_by_sport.py


def test_stats_by_sport(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    listed = tours(
        {'sport': 'hike', 'distance': 10_000, 'elevation_up': 500, 'time_in_motion': 7200},
        {'sport': 'hike', 'distance': 5_000, 'elevation_up': 100, 'time_in_motion': 3600},
        {'sport': 'padel', 'distance': 1_000, 'elevation_up': None, 'time_in_motion': None, 'duration': 600},
    )
    api.get(TOURS_URL, json=tour_page(listed))

    assert load_example('stats_by_sport')(['--year', '2025']) == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[1].split() == ['hike', '2', '15.0', '600', '3:00:00']
    assert lines[2].split() == ['padel', '1', '1.0', '0', '0:10:00']  # an unknown sport is kept
    query = query_of(api.calls[1].request)
    assert query['type'] == ['tour_recorded']
    assert query['start_date'] == ['2025-01-01T00:00:00.000Z']
    assert query['end_date'] == ['2025-12-31T23:59:59.000Z']


def test_stats_by_sport_without_tours(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    api.get(TOURS_URL, json=tour_page([]))

    assert load_example('stats_by_sport')([]) == 0

    assert 'No recorded tours found.' in capsys.readouterr().out


def test_stats_by_sport_reports_api_errors(
    load_example: Callable[[str], Main], api: responses.RequestsMock, capsys: pytest.CaptureFixture[str]
) -> None:
    api.get(TOURS_URL, status=404, json={'message': 'Not found'})

    assert load_example('stats_by_sport')([]) == 1

    assert 'Komoot request failed' in capsys.readouterr().out
