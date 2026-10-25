"""The ``kompy`` command line interface (``kompy.cli``), run in-process through :func:`kompy.cli.main`."""

from __future__ import annotations

import base64
import importlib
import io
import json
import logging
import os
import runpy
import sys
from pathlib import Path
from typing import Any

import pytest
import responses

from kompy import KomootConnector, __version__
from kompy.cli import EXIT_BROKEN_PIPE, EXIT_ERROR, EXIT_INTERRUPTED, EXIT_OK, EXIT_USAGE, _exit_code, main
from tests.conftest import (
    API,
    EMAIL,
    EXAMPLE_GPX,
    PASSWORD,
    TOKEN,
    USERNAME,
    json_body,
    make_tour,
    query_of,
    read_api_fixture,
    register_login,
    tour_page,
)

TOURS_URL = f'{API}/users/{USERNAME}/tours/'
USER_URL = f'{API}/users/{USERNAME}/'
UPLOAD_URL = f'{API}/tours/'
CREDENTIAL_VARIABLES = ('KOMOOT_EMAIL', 'KOMOOT_PASSWORD', 'KOMOOT_USERNAME', 'KOMOOT_TOKEN')


def tour_url(tour_id: int, suffix: str = '') -> str:
    """URL of a tour, optionally with a file suffix such as ``'.gpx'``."""
    return f'{API}/tours/{tour_id}{suffix}'


def api_queries(mock: responses.RequestsMock, fragment: str) -> list[dict[str, list[str]]]:
    """Query strings of the recorded requests whose URL contains ``fragment``."""
    return [query_of(call.request) for call in mock.calls if fragment in str(call.request.url)]


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    """Run the CLI and return its exit code, stdout and stderr."""
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure credentials of the developer's shell never reach the tests."""
    for name in CREDENTIAL_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Credentials as a username and token: no login request is sent."""
    monkeypatch.setenv('KOMOOT_USERNAME', USERNAME)
    monkeypatch.setenv('KOMOOT_TOKEN', TOKEN)


@pytest.fixture
def list_page() -> dict[str, Any]:
    """The real tour list page, reduced to a single page."""
    payload: dict[str, Any] = read_api_fixture('tours_list_page')
    payload['page']['totalPages'] = 1
    return payload


class FakeTerminal(io.StringIO):
    """A standard input that claims to be an interactive terminal."""

    def isatty(self) -> bool:
        return True


# ----------------------------------------------------------------- program, parsing and exit codes


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, '--version')

    assert code == EXIT_OK
    assert out.strip() == f'kompy {__version__}'


def test_help_lists_every_command(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, '--help')

    assert code == EXIT_OK
    for command in ('whoami', 'token', 'tours', 'upload'):
        assert command in out


@pytest.mark.parametrize(
    'argv',
    [
        pytest.param([], id='no command'),
        pytest.param(['tours'], id='no tour command'),
        pytest.param(['frobnicate'], id='unknown command'),
        pytest.param(['tours', 'list', '--limit', '0'], id='limit below 1'),
        pytest.param(['tours', 'list', '--limit', 'many'], id='limit not a number'),
        pytest.param(['tours', 'list', '--type', 'imagined'], id='unknown tour type'),
        pytest.param(['tours', 'list', '--status', 'secret'], id='unknown status'),
        pytest.param(['tours', 'show'], id='missing tour id'),
        pytest.param(['tours', 'download', '1'], id='missing destination'),
        pytest.param(['tours', 'download', '1', '--dest', 'x', '--format', 'kml'], id='unknown format'),
        pytest.param(['upload', 'walk.gpx', '--name', 'Walk'], id='missing sport'),
        pytest.param(['upload', 'walk.gpx', '--password', 'hunter2'], id='no password option'),
    ],
)
def test_usage_errors_exit_with_2(capsys: pytest.CaptureFixture[str], argv: list[str]) -> None:
    code, out, err = run(capsys, *argv)

    assert code == EXIT_USAGE
    assert out == ''
    assert 'usage: kompy' in err


def test_missing_credentials_are_explained(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, 'whoami')

    assert code == EXIT_ERROR
    assert out == ''
    assert err.startswith('error: No Komoot credentials found in the environment')
    assert 'KOMOOT_EMAIL and KOMOOT_PASSWORD' in err
    assert '--prompt-password' in err
    assert 'Traceback' not in err


def test_api_errors_exit_with_1_without_traceback(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(tour_url(404), status=404, json={'message': 'Tour not found'})

    code, out, err = run(capsys, 'tours', 'show', '404')

    assert code == EXIT_ERROR
    assert out == ''
    assert err.startswith('error: ')
    assert 'HTTP 404' in err
    assert 'Traceback' not in err


def test_debug_shows_traceback_and_debug_logs(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(tour_url(404), status=404)

    code, _, err = run(capsys, 'tours', 'show', '404', '--debug')

    assert code == EXIT_ERROR
    assert 'Traceback (most recent call last)' in err
    assert 'NotFoundError' in err
    assert 'debug: ' in err  # the kompy logger runs at DEBUG level
    assert err.rstrip().splitlines()[-1].startswith('error: ')


def test_debug_is_accepted_before_the_command(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(USER_URL, json=read_api_fixture('user'))

    code, _, err = run(capsys, '--debug', 'whoami')

    assert code == EXIT_OK
    assert 'debug: ' in err


def test_library_warnings_are_printed_to_stderr(
    capsys: pytest.CaptureFixture[str],
    token_env: None,
    mocked_responses: responses.RequestsMock,
    list_page: dict[str, Any],
) -> None:
    mocked_responses.get(TOURS_URL, json=list_page)

    code, _, err = run(capsys, 'tours', 'list', '--sport', 'moonwalk')

    assert code == EXIT_OK
    assert "warning: Unknown sport 'moonwalk'" in err
    assert 'debug: ' not in err


def test_logging_configuration_is_restored(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    logger = logging.getLogger('kompy')
    before = (logger.level, logger.propagate, list(logger.handlers))
    mocked_responses.get(USER_URL, json=read_api_fixture('user'))

    run(capsys, '--debug', 'whoami')

    assert (logger.level, logger.propagate, list(logger.handlers)) == before


def test_keyboard_interrupt_exits_with_130(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupt(*_args: Any, **_kwargs: Any) -> KomootConnector:
        raise KeyboardInterrupt

    monkeypatch.setattr(KomootConnector, 'from_env', interrupt)

    code, _, err = run(capsys, 'whoami')

    assert code == EXIT_INTERRUPTED
    assert err.strip() == 'interrupted'


@pytest.mark.parametrize(('code', 'expected'), [(None, 0), (0, 0), (2, 2), ('failure', 1)])
def test_exit_code_of_system_exit(code: str | int | None, expected: int) -> None:
    assert _exit_code(SystemExit(code)) == expected


def test_python_dash_m_runs_the_cli(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, 'argv', ['kompy', '--version'])

    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module('kompy', run_name='__main__', alter_sys=True)

    assert exit_info.value.code == EXIT_OK
    assert capsys.readouterr().out.strip() == f'kompy {__version__}'


def test_importing_the_main_module_does_not_run_the_cli(capsys: pytest.CaptureFixture[str]) -> None:
    sys.modules.pop('kompy.__main__', None)

    module = importlib.import_module('kompy.__main__')

    assert module.main is main
    assert capsys.readouterr() == ('', '')


# ----------------------------------------------------------------- credentials


def test_email_and_password_from_environment(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, mocked_responses: responses.RequestsMock
) -> None:
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', PASSWORD)
    register_login(mocked_responses)
    mocked_responses.get(USER_URL, json=read_api_fixture('user'))

    code, out, _ = run(capsys, 'whoami')

    assert code == EXIT_OK
    assert out == f'{USERNAME} (Sample display_name)\n'


def test_rejected_password_is_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, mocked_responses: responses.RequestsMock
) -> None:
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', 'wrong')
    register_login(mocked_responses, status=401, json={'message': 'Unauthorized'})

    code, _, err = run(capsys, 'whoami')

    assert code == EXIT_ERROR
    assert err.startswith('error: Komoot rejected the email address or password.')
    assert 'wrong' not in err


def test_invalid_email_is_reported(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('KOMOOT_EMAIL', 'not-an-email')
    monkeypatch.setenv('KOMOOT_PASSWORD', PASSWORD)

    code, _, err = run(capsys, 'whoami')

    assert code == EXIT_ERROR
    assert err.startswith('error: ')
    assert 'not-an-email' in err
    assert '--prompt-password' not in err  # credentials were found, they are just wrong


@pytest.mark.parametrize('email_from_env', [True, False])
def test_prompt_password(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    mocked_responses: responses.RequestsMock,
    email_from_env: bool,
) -> None:
    if email_from_env:
        monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', 'ignored-because-prompted')
    monkeypatch.setattr(sys, 'stdin', FakeTerminal(f'  {EMAIL}  \n'))
    prompts: list[str] = []

    def fake_getpass(prompt: str) -> str:
        prompts.append(prompt)
        return PASSWORD

    monkeypatch.setattr('getpass.getpass', fake_getpass)
    register_login(mocked_responses)
    mocked_responses.get(USER_URL, json=read_api_fixture('user'))

    code, out, _ = run(capsys, 'whoami', '--prompt-password')

    assert code == EXIT_OK
    assert prompts == ['Komoot password: ']
    assert ('Komoot email: ' in out) is not email_from_env
    login_auth = mocked_responses.calls[0].request.headers['Authorization']
    assert login_auth == 'Basic ' + base64.b64encode(f'{EMAIL}:{PASSWORD}'.encode()).decode()


def test_prompt_password_requires_a_terminal(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, 'stdin', io.StringIO(''))

    code, _, err = run(capsys, '--prompt-password', 'whoami')

    assert code == EXIT_ERROR
    assert err.strip() == 'error: --prompt-password needs an interactive terminal'


# ----------------------------------------------------------------- whoami and token


def test_whoami(capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.get(USER_URL, json=read_api_fixture('user'))

    code, out, err = run(capsys, 'whoami')

    assert code == EXIT_OK
    assert out == f'{USERNAME} (Sample display_name)\n'
    assert err == ''


def test_whoami_without_display_name(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    user = read_api_fixture('user')
    del user['display_name']
    mocked_responses.get(USER_URL, json=user)

    code, out, _ = run(capsys, 'whoami')

    assert code == EXIT_OK
    assert out == f'{USERNAME}\n'


def test_whoami_json(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(USER_URL, json=read_api_fixture('user'))

    code, out, _ = run(capsys, 'whoami', '--json')

    assert code == EXIT_OK
    assert json.loads(out) == read_api_fixture('user')


def test_token_prints_environment_variables_after_a_warning(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, mocked_responses: responses.RequestsMock
) -> None:
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', PASSWORD)
    register_login(mocked_responses)

    code, out, err = run(capsys, 'token')

    assert code == EXIT_OK
    assert out == f'KOMOOT_USERNAME={USERNAME}\nKOMOOT_TOKEN={TOKEN}\n'
    assert err.startswith('warning: the token below is equivalent to your password')
    assert TOKEN not in err


def test_token_values_are_shell_quoted(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, mocked_responses: responses.RequestsMock
) -> None:
    monkeypatch.setenv('KOMOOT_EMAIL', EMAIL)
    monkeypatch.setenv('KOMOOT_PASSWORD', PASSWORD)
    register_login(mocked_responses, json={**read_api_fixture('login'), 'password': 'a b$c'})

    code, out, _ = run(capsys, 'token')

    assert code == EXIT_OK
    assert out.splitlines()[1] == "KOMOOT_TOKEN='a b$c'"


# ----------------------------------------------------------------- tours list


def test_tours_list_table(
    capsys: pytest.CaptureFixture[str],
    token_env: None,
    mocked_responses: responses.RequestsMock,
    list_page: dict[str, Any],
) -> None:
    mocked_responses.get(TOURS_URL, json=list_page)

    code, out, err = run(capsys, 'tours', 'list')

    assert code == EXIT_OK
    assert err == ''
    assert out.splitlines() == [
        '        ID  DATE        SPORT    DISTANCE  DURATION  NAME',
        '1000000001  2026-10-24  jogging   12.0 km   1:02:33  Sample name',
        '3359786974  2026-10-21  jogging   11.0 km   0:56:59  Sample name',
        '3357935214  2026-10-20  jogging   13.0 km   1:08:51  Sample name',
    ]


def test_tours_list_sends_the_filters(
    capsys: pytest.CaptureFixture[str],
    token_env: None,
    mocked_responses: responses.RequestsMock,
    list_page: dict[str, Any],
) -> None:
    mocked_responses.get(TOURS_URL, json=list_page)

    code, out, _ = run(
        capsys,
        'tours',
        'list',
        '--type',
        'recorded',
        '--sport',
        'jogging',
        '--sport',
        'hike',
        '--status',
        'friends',
        '--limit',
        '2',
        '--name',
        'Sample',
    )

    assert code == EXIT_OK
    assert len(out.splitlines()) == 3  # header + 2 tours
    (query,) = api_queries(mocked_responses, '/tours/')
    assert query['type'] == ['tour_recorded']
    assert query['sport_types'] == ['jogging,hike']
    assert query['status'] == ['friends']
    assert query['name'] == ['Sample']


def test_tours_list_json_lines(
    capsys: pytest.CaptureFixture[str],
    token_env: None,
    mocked_responses: responses.RequestsMock,
    list_page: dict[str, Any],
) -> None:
    mocked_responses.get(TOURS_URL, json=list_page)

    code, out, _ = run(capsys, 'tours', 'list', '--json')

    assert code == EXIT_OK
    lines = out.splitlines()
    assert [json.loads(line) for line in lines] == list_page['_embedded']['tours']


def test_tours_list_empty(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([], total_pages=0))

    code, out, err = run(capsys, 'tours', 'list')

    assert code == EXIT_OK
    assert out == ''
    assert err == 'No tours found.\n'


def test_tours_list_missing_values_and_long_names(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    long_name = 'A very long tour name ' * 5
    sparse = make_tour(7, name=None, date=None, sport=None, distance=None, duration=None)
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(6, name=long_name), sparse]))

    code, out, _ = run(capsys, 'tours', 'list')

    assert code == EXIT_OK
    _, long_row, sparse_row = out.splitlines()
    assert long_row.endswith(f'{long_name[:57]}...')
    assert sparse_row.split() == ['7', '-', '-', '-', '-', '-']


# ----------------------------------------------------------------- tours show


def test_tours_show(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(tour_url(1000000001), json=read_api_fixture('tour_recorded_by_id'))

    code, out, _ = run(capsys, 'tours', 'show', '1000000001')

    assert code == EXIT_OK
    assert out.splitlines() == [
        'Name:           Sample name',
        'ID:             1000000001',
        'URL:            https://www.komoot.com/tour/1000000001',
        'Type:           recorded',
        'Sport:          jogging',
        'Status:         friends',
        'Date:           2026-10-24 12:46+00:00',
        'Distance:       12.0 km',
        'Duration:       1:02:33',
        'Time in motion: 1:02:33',
        'Elevation:      +56 m / -53 m',
    ]


def test_tours_show_with_missing_values(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(tour_url(9), json={'id': 9})

    code, out, _ = run(capsys, 'tours', 'show', '9')

    assert code == EXIT_OK
    values = [line.split(':', 1)[1].strip() for line in out.splitlines()]
    assert values == ['-', '9', 'https://www.komoot.com/tour/9', '-', '-', '-', '-', '-', '-', '-', '-']


def test_tours_show_json(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    payload = read_api_fixture('tour_planned_by_id')
    mocked_responses.get(tour_url(payload['id']), json=payload)

    code, out, _ = run(capsys, 'tours', 'show', str(payload['id']), '--json')

    assert code == EXIT_OK
    assert json.loads(out) == payload


# ----------------------------------------------------------------- tours download


def test_download_by_ids(
    capsys: pytest.CaptureFixture[str],
    token_env: None,
    mocked_responses: responses.RequestsMock,
    tmp_path: Path,
) -> None:
    mocked_responses.get(tour_url(1, '.gpx'), body=b'<gpx>1</gpx>')
    mocked_responses.get(tour_url(2, '.gpx'), body=b'<gpx>2</gpx>')
    destination = tmp_path / 'new' / 'dir'

    code, out, err = run(capsys, 'tours', 'download', '1', '2', '--dest', str(destination))

    assert code == EXIT_OK
    assert err == ''
    assert (destination / '1.gpx').read_bytes() == b'<gpx>1</gpx>'
    assert (destination / '2.gpx').read_bytes() == b'<gpx>2</gpx>'
    assert out.splitlines() == [
        f'downloaded  {destination / "1.gpx"}',
        f'downloaded  {destination / "2.gpx"}',
        '2 downloaded, 0 skipped, 0 failed.',
    ]


def test_download_skips_existing_files(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    (tmp_path / '1.gpx').write_bytes(b'old')

    code, out, _ = run(capsys, 'tours', 'download', '1', '--dest', str(tmp_path))

    assert code == EXIT_OK
    assert (tmp_path / '1.gpx').read_bytes() == b'old'
    assert out.splitlines() == [
        f'skipped     {tmp_path / "1.gpx"} (already exists)',
        '0 downloaded, 1 skipped, 0 failed.',
    ]


def test_download_overwrite(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    (tmp_path / '1.gpx').write_bytes(b'old')
    mocked_responses.get(tour_url(1, '.gpx'), body=b'new')

    code, _, _ = run(capsys, 'tours', 'download', '1', '--dest', str(tmp_path), '--overwrite')

    assert code == EXIT_OK
    assert (tmp_path / '1.gpx').read_bytes() == b'new'


def test_download_failures_exit_with_1_after_the_other_downloads(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(tour_url(1, '.gpx'), status=404)
    mocked_responses.get(tour_url(2, '.gpx'), body=b'<gpx/>')

    code, out, err = run(capsys, 'tours', 'download', '1', '2', '--dest', str(tmp_path))

    assert code == EXIT_ERROR
    assert err.startswith('error: tour 1: ')
    assert out.splitlines()[-1] == '1 downloaded, 0 skipped, 1 failed.'
    assert (tmp_path / '2.gpx').exists()
    assert not (tmp_path / '1.gpx').exists()


def test_download_all_names_files_after_the_tours(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1, name='Über den Säntis!'), make_tour(2)]))
    mocked_responses.get(tour_url(1, '.gpx'), body=b'<gpx/>')
    mocked_responses.get(tour_url(2, '.gpx'), status=403)

    code, out, err = run(capsys, 'tours', 'download', '--all', '--dest', str(tmp_path))

    assert code == EXIT_ERROR
    assert (tmp_path / '1_uber-den-santis.gpx').read_bytes() == b'<gpx/>'
    assert 'error: tour 2: ' in err
    assert out.splitlines()[-1] == '1 downloaded, 0 skipped, 1 failed.'


def test_download_with_filters(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1, name='Walk')]))
    mocked_responses.get(tour_url(1, '.gpx'), body=b'<gpx/>')

    code, _, _ = run(capsys, 'tours', 'download', '--sport', 'hike', '--limit', '1', '--dest', str(tmp_path))

    assert code == EXIT_OK
    assert (tmp_path / '1_walk.gpx').exists()
    (query,) = api_queries(mocked_responses, f'/users/{USERNAME}/tours/')
    assert query['sport_types'] == ['hike']
    assert query['limit'] == ['1']


def test_download_fit_selects_planned_tours(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(3, name='Plan', type='tour_planned')]))
    mocked_responses.get(tour_url(3, '.fit'), body=b'FIT')

    code, out, err = run(capsys, 'tours', 'download', '--all', '--format', 'fit', '--dest', str(tmp_path))

    assert code == EXIT_OK
    assert err.startswith('note: FIT files are only available for planned tours')
    assert (tmp_path / '3_plan.fit').read_bytes() == b'FIT'
    assert out.splitlines()[-1] == '1 downloaded, 0 skipped, 0 failed.'
    (query,) = api_queries(mocked_responses, f'/users/{USERNAME}/tours/')
    assert query['type'] == ['tour_planned']


def test_download_fit_of_a_recorded_tour_by_id_fails_clearly(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(tour_url(5, '.fit'), status=400, body=b'')

    code, _, err = run(capsys, 'tours', 'download', '5', '--format', 'fit', '--dest', str(tmp_path))

    assert code == EXIT_ERROR
    assert 'only provides FIT files for planned tours' in err


@pytest.mark.parametrize(
    ('arguments', 'message'),
    [
        pytest.param([], 'give tour IDs, filters, or --all', id='nothing selected'),
        pytest.param(['1', '--all'], 'not both', id='ids and --all'),
        pytest.param(['1', '--sport', 'hike'], 'not both', id='ids and filters'),
        pytest.param(
            ['--type', 'recorded', '--format', 'fit'], 'only available for planned tours', id='fit of recorded tours'
        ),
    ],
)
def test_download_argument_conflicts_are_usage_errors(
    capsys: pytest.CaptureFixture[str], token_env: None, tmp_path: Path, arguments: list[str], message: str
) -> None:
    code, out, err = run(capsys, 'tours', 'download', *arguments, '--dest', str(tmp_path))

    assert code == EXIT_USAGE
    assert out == ''
    assert 'usage: kompy tours download' in err
    assert 'kompy tours download: error: ' in err
    assert message in err


def test_download_destination_must_be_a_directory(
    capsys: pytest.CaptureFixture[str], token_env: None, tmp_path: Path
) -> None:
    file = tmp_path / 'file.txt'
    file.write_text('not a directory')

    code, _, err = run(capsys, 'tours', 'download', '1', '--dest', str(file))

    assert code == EXIT_ERROR
    assert err.strip() == f'error: {file} is not a directory'


# ----------------------------------------------------------------- upload


def test_upload(capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42, 'status': 'friends'})

    code, out, _ = run(capsys, 'upload', str(EXAMPLE_GPX), '--sport', 'hike', '--name', 'Morning walk')

    assert code == EXIT_OK
    assert out == 'Uploaded tour 42: https://www.komoot.com/tour/42\n'
    request = mocked_responses.calls[0].request
    assert query_of(request) == {
        'data_type': ['gpx'],
        'sport': ['hike'],
        'name': ['Morning walk'],
        'status': ['friends'],  # the library default
    }
    assert request.body == EXAMPLE_GPX.read_bytes()


def test_upload_with_status(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.post(UPLOAD_URL, status=201, json={'id': 42, 'status': 'friends'})  # Komoot ignores it
    mocked_responses.patch(f'{API}/tours/42', json={'id': 42, 'status': 'private'})

    code, _, _ = run(capsys, 'upload', str(EXAMPLE_GPX), '--sport', 'hike', '--name', 'Walk', '--status', 'private')

    assert code == EXIT_OK
    assert query_of(mocked_responses.calls[0].request)['status'] == ['private']
    assert json_body(mocked_responses.calls[1].request) == {'status': 'private'}  # applied afterwards


def test_upload_duplicate(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.post(UPLOAD_URL, status=202, json={'id': 7})

    code, out, _ = run(capsys, 'upload', str(EXAMPLE_GPX), '--sport', 'hike', '--name', 'Walk')

    assert code == EXIT_OK
    assert out == 'Komoot already had this tour, nothing was uploaded: https://www.komoot.com/tour/7\n'


def test_upload_missing_file(capsys: pytest.CaptureFixture[str], token_env: None, tmp_path: Path) -> None:
    missing = tmp_path / 'missing.gpx'

    code, _, err = run(capsys, 'upload', str(missing), '--sport', 'hike', '--name', 'Walk')

    assert code == EXIT_ERROR
    assert err.strip() == f'error: {missing} is not a file'


def test_upload_unsupported_file_type(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    notes = tmp_path / 'notes.txt'
    notes.write_text('hello')

    code, _, err = run(capsys, 'upload', str(notes), '--sport', 'hike', '--name', 'Walk')

    assert code == EXIT_ERROR
    assert err.strip() == 'error: Cannot upload notes.txt: the file must end in .gpx, .fit or .tcx.'


def test_upload_rejected_by_komoot(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.post(UPLOAD_URL, status=400, json={'message': 'Invalid GPX'})

    code, out, err = run(capsys, 'upload', str(EXAMPLE_GPX), '--sport', 'hike', '--name', 'Walk')

    assert code == EXIT_ERROR
    assert out == ''
    assert err.startswith('error: ')
    assert 'HTTP 400' in err


def test_download_fit_of_planned_tours_needs_no_note(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([]))

    code, out, err = run(capsys, 'tours', 'download', '--type', 'planned', '--format', 'fit', '--dest', str(tmp_path))

    assert code == EXIT_OK
    assert err == ''
    assert out == '0 downloaded, 0 skipped, 0 failed.\n'


# ----------------------------------------------------------------- regressions


@pytest.mark.parametrize('json_output', [False, True])
def test_broken_pipe_exits_quietly(
    capsys: pytest.CaptureFixture[str],
    token_env: None,
    mocked_responses: responses.RequestsMock,
    monkeypatch: pytest.MonkeyPatch,
    json_output: bool,
) -> None:
    # `kompy tours list | head`: the reader goes away while kompy is still printing.
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1), make_tour(2)]))

    def closed_pipe(*_args: object, **_kwargs: object) -> None:
        raise BrokenPipeError(32, 'Broken pipe')

    monkeypatch.setattr('builtins.print', closed_pipe)
    argv = ['tours', 'list', '--json'] if json_output else ['tours', 'list']

    code = main(argv)

    monkeypatch.undo()
    assert code == EXIT_BROKEN_PIPE == 141
    assert capsys.readouterr().err == ''  # no "error: [Errno 32] Broken pipe"


def test_broken_pipe_redirects_stdout_to_devnull(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from kompy import cli

    with (tmp_path / 'out').open('w') as stdout:
        monkeypatch.setattr(sys, 'stdout', stdout)
        saved = os.dup(stdout.fileno())
        cli._silence_stdout()
        stdout.write('dropped')
        stdout.flush()
        os.dup2(saved, stdout.fileno())
        os.close(saved)

    assert (tmp_path / 'out').read_text() == ''


def test_ctrl_d_at_the_prompt_is_an_interruption(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, 'stdin', FakeTerminal(''))  # input() raises EOFError on an empty terminal

    code, _, err = run(capsys, 'whoami', '--prompt-password')

    assert code == EXIT_INTERRUPTED
    assert err.strip() == 'interrupted'


def test_global_options_are_accepted_after_the_tours_group(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([]))

    code, _, err = run(capsys, 'tours', '--debug', 'list')

    assert code == EXIT_OK
    assert 'unrecognized arguments' not in err
    assert 'GET https://api.komoot.de/v007/users/' in err  # debug logging is on


def test_download_by_id_skips_a_tour_downloaded_with_all(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    (tmp_path / '1_morning-walk.gpx').write_bytes(b'old')

    code, out, _ = run(capsys, 'tours', 'download', '1', '--dest', str(tmp_path))

    assert code == EXIT_OK
    assert out.splitlines()[0] == f'skipped     {tmp_path / "1_morning-walk.gpx"} (already exists)'
    assert not (tmp_path / '1.gpx').exists()


def test_download_all_skips_a_tour_downloaded_by_id(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(TOURS_URL, json=tour_page([make_tour(1, name='Renamed')]))
    (tmp_path / '1.gpx').write_bytes(b'old')

    code, out, _ = run(capsys, 'tours', 'download', '--all', '--dest', str(tmp_path))

    assert code == EXIT_OK
    assert out.splitlines() == [
        f'skipped     {tmp_path / "1.gpx"} (already exists)',
        '0 downloaded, 1 skipped, 0 failed.',
    ]


def test_download_error_does_not_repeat_the_tour_id(
    capsys: pytest.CaptureFixture[str], token_env: None, mocked_responses: responses.RequestsMock, tmp_path: Path
) -> None:
    mocked_responses.get(tour_url(5, '.fit'), status=400, body=b'')

    _, _, err = run(capsys, 'tours', 'download', '5', '--format', 'fit', '--dest', str(tmp_path))

    assert err.startswith('error: Tour 5 cannot be exported as FIT')
