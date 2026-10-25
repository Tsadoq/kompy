"""
The ``kompy`` command line interface.

Run ``kompy --help`` (or ``python -m kompy --help``) for the list of commands. Credentials come from the
environment, never from command line arguments:

- ``KOMOOT_USERNAME`` and ``KOMOOT_TOKEN`` (see ``kompy token``), or
- ``KOMOOT_EMAIL`` and ``KOMOOT_PASSWORD``.

With ``--prompt-password`` the password is asked for interactively instead (the email address is read from
``KOMOOT_EMAIL`` or asked for as well).

Exit codes: ``0`` on success, ``1`` when a request or a file operation fails (or some downloads failed), ``2`` on a
usage error, ``130`` when interrupted, ``141`` when the output was cut short (e.g. piped into ``head``).
"""

from __future__ import annotations

import argparse
import contextlib
import getpass
import json
import logging
import os
import re
import shlex
import sys
import traceback
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path
from typing import Any, Final, TypedDict

from kompy import __version__
from kompy.constants import PrivacyStatus, TourTypes
from kompy.exceptions import KomootError
from kompy.komoot_connector import KomootConnector, find_downloaded_tour, tour_filename
from kompy.tour import Tour

__all__ = ['EXIT_BROKEN_PIPE', 'EXIT_ERROR', 'EXIT_INTERRUPTED', 'EXIT_OK', 'EXIT_USAGE', 'build_parser', 'main']

EXIT_OK: Final[int] = 0
"""Exit code of a successful command."""
EXIT_ERROR: Final[int] = 1
"""Exit code when a request, a file operation or some downloads failed."""
EXIT_USAGE: Final[int] = 2
"""Exit code of a usage error (invalid arguments)."""
EXIT_INTERRUPTED: Final[int] = 130
"""Exit code when the command is interrupted with Ctrl+C (or Ctrl+D at a prompt)."""
EXIT_BROKEN_PIPE: Final[int] = 141
"""Exit code when the reader of the output went away (128 + SIGPIPE, like other command line tools)."""

ENV_PREFIX: Final[str] = 'KOMOOT_'
"""Prefix of the environment variables holding the credentials."""

_TOUR_TYPES: Final[dict[str, TourTypes]] = {'planned': TourTypes.TOUR_PLANNED, 'recorded': TourTypes.TOUR_RECORDED}
_STATUSES: Final[list[str]] = PrivacyStatus.list_all()
_FORMATS: Final[tuple[str, ...]] = ('gpx', 'fit')
_MAX_NAME_WIDTH: Final[int] = 60
_MISSING: Final[str] = '-'
_DEBUG_FORMAT: Final[str] = '%(asctime)s %(name)s: %(message)s'
_CREDENTIAL_NOTICE: Final[str] = (
    'warning: the token below is equivalent to your password and stays valid after new logins. '
    'Store it like a password (e.g. in a password manager or a secret store), never in version control.'
)

Handler = Callable[[argparse.Namespace], int]


class _TourFilters(TypedDict):
    """The tour filters of the command line, as keyword arguments of :meth:`KomootConnector.iter_tours`."""

    limit: int | None
    tour_type: str | None
    sport_types: list[str] | None
    status: str | None
    tour_name: str | None


class UsageError(Exception):
    """Arguments that are valid one by one but not together; reported like an argparse error (exit code 2)."""


class CliError(Exception):
    """A failure to report to the user without a traceback (exit code 1)."""


# ----------------------------------------------------------------- entry point


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the ``kompy`` command line interface.

    :param argv: The arguments, without the program name; ``sys.argv[1:]`` when ``None``.
    :return: The exit code (see the module documentation).
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_request:  # --help, --version and usage errors
        return _exit_code(exit_request)

    handler: Handler = args.handler
    with _cli_logging(debug=args.debug):
        try:
            return handler(args)
        except UsageError as error:
            command_parser: argparse.ArgumentParser = args.command_parser
            command_parser.print_usage(sys.stderr)
            print(f'{command_parser.prog}: error: {error}', file=sys.stderr)
            return EXIT_USAGE
        except (KeyboardInterrupt, EOFError):  # Ctrl+C, or Ctrl+D at a prompt
            print('\ninterrupted', file=sys.stderr)
            return EXIT_INTERRUPTED
        except BrokenPipeError:  # e.g. `kompy tours list | head`: not an error
            _silence_stdout()
            return EXIT_BROKEN_PIPE
        except (KomootError, CliError, OSError, ValueError) as error:
            if args.debug:
                traceback.print_exception(error, file=sys.stderr)
            print(f'error: {error}', file=sys.stderr)
            return EXIT_ERROR


def _silence_stdout() -> None:
    """Point stdout at the null device, so Python does not fail again flushing it at exit."""
    with contextlib.suppress(OSError, ValueError, AttributeError):
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        os.close(devnull)


def build_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser of the ``kompy`` command.

    :return: The parser; each command stores its handler in the ``handler`` attribute of the parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog='kompy',
        description='Work with your Komoot tours from the command line.',
        epilog=(
            'Credentials are read from KOMOOT_USERNAME and KOMOOT_TOKEN (see "kompy token"), '
            'or from KOMOOT_EMAIL and KOMOOT_PASSWORD.'
        ),
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    _add_global_options(parser, default=False)
    commands = parser.add_subparsers(title='commands', metavar='COMMAND', required=True)

    whoami = _add_command(commands, 'whoami', _cmd_whoami, help='show the logged-in user')
    whoami.add_argument('--json', action='store_true', help='print the user profile as JSON')

    _add_command(commands, 'token', _cmd_token, help='print the username and API token as environment variables')

    tours_parser = commands.add_parser('tours', help='list, show and download tours')
    _add_global_options(tours_parser, default=argparse.SUPPRESS)  # `kompy tours --debug list` works too
    tours = tours_parser.add_subparsers(title='tour commands', metavar='COMMAND', required=True)

    filters = argparse.ArgumentParser(add_help=False)
    group = filters.add_argument_group('filters')
    group.add_argument('--type', choices=sorted(_TOUR_TYPES), help='only planned or only recorded tours')
    group.add_argument(
        '--sport',
        action='append',
        metavar='SPORT',
        help='only tours of this sport, e.g. hike or touringbicycle (repeat for several sports)',
    )
    group.add_argument('--status', choices=_STATUSES, help='only tours with this visibility')
    group.add_argument('--limit', type=_positive_int, metavar='N', help='at most N tours')
    group.add_argument('--name', metavar='TEXT', help='only tours whose name contains TEXT (case-insensitive)')

    tours_list = _add_command(tours, 'list', _cmd_tours_list, parents=[filters], help='list your tours')
    tours_list.add_argument('--json', action='store_true', help='print each tour as one line of JSON')

    show = _add_command(tours, 'show', _cmd_tours_show, help='show the details of a tour')
    show.add_argument('tour_id', type=_positive_int, metavar='ID', help='the id of the tour')
    show.add_argument('--json', action='store_true', help='print the tour as returned by the Komoot API')

    download = _add_command(
        tours,
        'download',
        _cmd_tours_download,
        parents=[filters],
        help='download tours as GPX or FIT files',
        description=(
            'Download the given tours, or the tours selected by --all or the filters. '
            'Existing files are skipped unless --overwrite is given.'
        ),
    )
    download.add_argument('tour_ids', nargs='*', type=_positive_int, metavar='ID', help='ids of the tours')
    download.add_argument('--format', choices=_FORMATS, default='gpx', help='file format (default: gpx)')
    download.add_argument('--dest', type=Path, required=True, metavar='DIR', help='directory to save the files in')
    download.add_argument('--all', action='store_true', help='download all your tours (combinable with filters)')
    download.add_argument('--overwrite', action='store_true', help='download tours whose file already exists again')

    upload = _add_command(commands, 'upload', _cmd_upload, help='upload a .gpx, .fit or .tcx file as a new tour')
    upload.add_argument('file', type=Path, metavar='FILE', help='the file to upload')
    upload.add_argument('--sport', required=True, help='the sport of the tour, e.g. hike')
    upload.add_argument('--name', required=True, help='the name of the tour')
    upload.add_argument('--status', choices=_STATUSES, help='the visibility of the tour (default: friends)')

    return parser


# ----------------------------------------------------------------- commands


def _cmd_whoami(args: argparse.Namespace) -> int:
    """Print the username and display name of the logged-in user."""
    with _connect(args) as connector:
        user = connector.get_user()
    if args.json:
        print(json.dumps(user.raw, indent=2))
    elif user.display_name:
        print(f'{user.username} ({user.display_name})')
    else:
        print(user.username)
    return EXIT_OK


def _cmd_token(args: argparse.Namespace) -> int:
    """Print the username and token as ``KEY=value`` lines, ready to store as environment variables."""
    with _connect(args) as connector:
        username, token = connector.username, connector.token
    print(_CREDENTIAL_NOTICE, file=sys.stderr)
    print(f'{ENV_PREFIX}USERNAME={shlex.quote(username)}')
    print(f'{ENV_PREFIX}TOKEN={shlex.quote(token)}')
    return EXIT_OK


def _cmd_tours_list(args: argparse.Namespace) -> int:
    """Print the selected tours as a table, or as JSON lines."""
    with _connect(args) as connector:
        tours = connector.iter_tours(**_tour_filters(args))
        if args.json:
            for tour in tours:  # streamed, one page at a time
                print(json.dumps(tour.to_dict()))
            return EXIT_OK
        rows = [_tour_row(tour) for tour in tours]
    if not rows:
        print('No tours found.', file=sys.stderr)
        return EXIT_OK
    headers = ('ID', 'DATE', 'SPORT', 'DISTANCE', 'DURATION', 'NAME')
    for line in _format_table(headers, rows, right_aligned={0, 3, 4}):
        print(line)
    return EXIT_OK


def _cmd_tours_show(args: argparse.Namespace) -> int:
    """Print the details of one tour."""
    with _connect(args) as connector:
        tour = connector.get_tour_by_id(args.tour_id)
    if args.json:
        print(json.dumps(tour.to_dict(), indent=2))
        return EXIT_OK
    elevation = _MISSING
    if tour.elevation_up is not None or tour.elevation_down is not None:
        elevation = f'+{_format_meters(tour.elevation_up)} / -{_format_meters(tour.elevation_down)}'
    details = {
        'Name': tour.name or _MISSING,
        'ID': str(tour.id),
        'URL': tour.url,
        'Type': _format_type(tour.type),
        'Sport': _or_missing(tour.sport),
        'Status': _or_missing(tour.status),
        'Date': tour.start_date.isoformat(sep=' ', timespec='minutes') if tour.start_date else _MISSING,
        'Distance': _format_km(tour.distance_km),
        'Duration': _format_duration(tour.total_duration),
        'Time in motion': _format_duration(tour.time_in_motion),
        'Elevation': elevation,
    }
    width = max(map(len, details)) + 1
    for label, value in details.items():
        print(f'{label + ":":<{width}} {value}')
    return EXIT_OK


def _cmd_tours_download(args: argparse.Namespace) -> int:
    """Download the given or the selected tours into a directory, and print a summary."""
    filters = _tour_filters(args)
    has_filters = any(value is not None for value in filters.values())
    if args.tour_ids and (args.all or has_filters):
        raise UsageError('give either tour IDs or --all/filters, not both')
    if not args.tour_ids and not (args.all or has_filters):
        raise UsageError('give tour IDs, filters, or --all to download all your tours')
    if args.format == 'fit' and not args.tour_ids:
        if filters['tour_type'] == TourTypes.TOUR_RECORDED:
            raise UsageError('FIT files are only available for planned tours; use --format gpx for recorded tours')
        if filters['tour_type'] is None:
            print('note: FIT files are only available for planned tours; selecting planned tours.', file=sys.stderr)
            filters['tour_type'] = TourTypes.TOUR_PLANNED

    destination: Path = args.dest
    if destination.exists() and not destination.is_dir():
        raise CliError(f'{destination} is not a directory')
    destination.mkdir(parents=True, exist_ok=True)

    downloaded = skipped = failed = 0
    with _connect(args) as connector:
        targets: Iterable[int | Tour] = args.tour_ids or connector.iter_tours(**filters)
        for target in targets:
            tour_id = target.id if isinstance(target, Tour) else target
            path = destination / tour_filename(target, args.format)
            # A tour downloaded by id is named <id>.<fmt>, and by --all <id>_<name>.<fmt>: either one counts.
            existing = None if args.overwrite else find_downloaded_tour(destination, tour_id, args.format)
            if existing is not None:
                print(f'skipped     {existing} (already exists)')
                skipped += 1
                continue
            try:
                connector.download_tour(target, path, args.format)
            except KomootError as error:
                message = str(error)
                named = re.search(rf'\btour {tour_id}\b', message, re.IGNORECASE)  # already says which tour
                prefix = '' if named else f'tour {tour_id}: '
                print(f'error: {prefix}{message}', file=sys.stderr)
                failed += 1
                continue
            print(f'downloaded  {path}')
            downloaded += 1
    print(f'{downloaded} downloaded, {skipped} skipped, {failed} failed.')
    return EXIT_ERROR if failed else EXIT_OK


def _cmd_upload(args: argparse.Namespace) -> int:
    """Upload a file as a new tour."""
    file: Path = args.file
    if not file.is_file():
        raise CliError(f'{file} is not a file')
    with _connect(args) as connector:
        if args.status is None:  # keep the library's default visibility
            result = connector.upload_tour(file, args.sport, args.name)
        else:
            result = connector.upload_tour(file, args.sport, args.name, status=args.status)
    url = f'https://www.komoot.com/tour/{result.tour_id}'
    if result.created:
        print(f'Uploaded tour {result.tour_id}: {url}')
    else:
        print(f'Komoot already had this tour, nothing was uploaded: {url}')
    return EXIT_OK


# ----------------------------------------------------------------- helpers: setup


def _add_command(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    handler: Handler,
    **options: Any,
) -> argparse.ArgumentParser:
    """
    Add a command whose parser and handler are stored in the parsed arguments.

    The global options are accepted after the command too (``kompy tours list --debug``).
    """
    common = argparse.ArgumentParser(add_help=False)
    _add_global_options(common, default=argparse.SUPPRESS)  # don't override a value given before the command
    options['parents'] = [*options.get('parents', []), common]
    summary = options.get('help')
    if summary and 'description' not in options:  # show the one-line help on top of the command's own --help
        options['description'] = f'{summary[0].upper()}{summary[1:]}.'
    command = commands.add_parser(name, **options)
    command.set_defaults(handler=handler, command_parser=command)
    return command


def _add_global_options(parser: argparse.ArgumentParser, *, default: object) -> None:
    """Add the options that apply to every command."""
    parser.add_argument(
        '--debug', action='store_true', default=default, help='log debug messages and show tracebacks of errors'
    )
    parser.add_argument(
        '--prompt-password',
        action='store_true',
        default=default,
        help='ask for the password interactively instead of reading KOMOOT_PASSWORD',
    )


def _connect(args: argparse.Namespace) -> KomootConnector:
    """
    Create a connector from the environment, or with a password typed in by the user.

    :raises CliError: If no credentials are available.
    """
    if args.prompt_password:
        if not sys.stdin.isatty():
            raise CliError('--prompt-password needs an interactive terminal')
        # Ctrl+D at a prompt raises EOFError, which main() reports like an interruption.
        email = os.environ.get(f'{ENV_PREFIX}EMAIL') or input('Komoot email: ').strip()
        return KomootConnector(email, getpass.getpass('Komoot password: '))
    try:
        return KomootConnector.from_env(ENV_PREFIX)
    except KomootError:
        raise
    except ValueError as error:  # no credentials in the environment
        raise CliError(f'{error} Or run with --prompt-password to type the password in.') from error


@contextlib.contextmanager
def _cli_logging(*, debug: bool) -> Iterator[None]:
    """Print the warnings (or, with ``debug``, all messages) of kompy to stderr while a command runs."""
    logger = logging.getLogger('kompy')
    saved_level, saved_propagate = logger.level, logger.propagate
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_CliFormatter(_DEBUG_FORMAT if debug else '%(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.WARNING)
    logger.propagate = False  # fit_tool configures the root logger; avoid printing messages twice
    try:
        yield
    finally:
        logger.removeHandler(handler)
        logger.setLevel(saved_level)
        logger.propagate = saved_propagate


class _CliFormatter(logging.Formatter):
    """Prefix messages with their lowercase level, like ``warning: ...``."""

    def format(self, record: logging.LogRecord) -> str:
        return f'{record.levelname.lower()}: {super().format(record)}'


def _exit_code(exit_request: SystemExit) -> int:
    """Turn the ``SystemExit`` raised by argparse into an exit code."""
    code = exit_request.code
    if code is None:
        return EXIT_OK
    return code if isinstance(code, int) else EXIT_ERROR


def _positive_int(value: str) -> int:
    """Parse a command line value that must be a whole number greater than 0."""
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f'not a whole number: {value!r}') from None
    if number < 1:
        raise argparse.ArgumentTypeError(f'must be 1 or greater: {value!r}')
    return number


def _tour_filters(args: argparse.Namespace) -> _TourFilters:
    """Translate the filter options into keyword arguments of :meth:`KomootConnector.iter_tours`."""
    return {
        'limit': args.limit,
        'tour_type': _TOUR_TYPES[args.type] if args.type else None,
        'sport_types': args.sport,
        'status': args.status,
        'tour_name': args.name,
    }


# ----------------------------------------------------------------- helpers: formatting


def _tour_row(tour: Tour) -> tuple[str, ...]:
    """Format a tour as a row of the tour table."""
    name = tour.name or _MISSING
    if len(name) > _MAX_NAME_WIDTH:
        name = f'{name[: _MAX_NAME_WIDTH - 3]}...'
    return (
        str(tour.id),
        tour.start_date.date().isoformat() if tour.start_date else _MISSING,
        _or_missing(tour.sport),
        _format_km(tour.distance_km),
        _format_duration(tour.total_duration),
        name,
    )


def _format_table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, right_aligned: set[int]) -> list[str]:
    """Lay out rows as aligned text columns, the last column without trailing padding."""
    widths = [max(len(row[index]) for row in [headers, *rows]) for index in range(len(headers))]

    def line(cells: Sequence[str]) -> str:
        padded = [
            cell.rjust(width) if index in right_aligned else cell.ljust(width)
            for index, (cell, width) in enumerate(zip(cells, widths, strict=True))
        ]
        return '  '.join(padded).rstrip()

    return [line(headers), *(line(row) for row in rows)]


def _format_km(kilometers: float | None) -> str:
    """Format a distance in kilometers with one decimal."""
    return _MISSING if kilometers is None else f'{kilometers:.1f} km'


def _format_meters(meters: float | None) -> str:
    """Format a height difference in whole meters."""
    return _MISSING if meters is None else f'{meters:.0f} m'


def _format_duration(seconds: int | None) -> str:
    """Format a duration in seconds as ``H:MM:SS``."""
    if seconds is None:
        return _MISSING
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f'{hours}:{minutes:02}:{seconds:02}'


def _format_type(tour_type: str | None) -> str:
    """Format a tour type without its ``tour_`` prefix (``'tour_planned'`` becomes ``'planned'``)."""
    return _MISSING if tour_type is None else str(tour_type).removeprefix('tour_')


def _or_missing(value: str | None) -> str:
    """Format an optional text value."""
    return _MISSING if value is None else str(value)
