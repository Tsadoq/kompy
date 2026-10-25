"""
Back up your Komoot tours: download every tour as a GPX (or FIT) file into a folder.

Files are named ``<id>_<name>.<fmt>``. Tours whose file already exists are skipped, so you can re-run the script
to resume an interrupted backup or to fetch only the tours added since the last run.

Credentials are read from the environment: ``KOMOOT_EMAIL`` and ``KOMOOT_PASSWORD``, or ``KOMOOT_USERNAME`` and
``KOMOOT_TOKEN``.

Examples::

    python examples/export_all_tours.py komoot-backup
    python examples/export_all_tours.py komoot-backup --recorded-only --since 2024-01-01
    python examples/export_all_tours.py komoot-routes --format fit    # FIT exists only for planned tours

This script only reads data; it never changes anything on your account.
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

from kompy import DownloadError, KomootConnector, KomootError, TourTypes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('dest_dir', help='folder to write the files to (created if missing)')
    parser.add_argument('--format', choices=['gpx', 'fit'], default='gpx', help='file format (default: gpx)')
    kind = parser.add_mutually_exclusive_group()
    kind.add_argument('--recorded-only', action='store_true', help='only recorded activities')
    kind.add_argument('--planned-only', action='store_true', help='only planned routes')
    parser.add_argument('--since', metavar='YYYY-MM-DD', help='only tours from this date on')
    parser.add_argument('--overwrite', action='store_true', help='download files that already exist again')
    args = parser.parse_args(argv)
    if args.recorded_only and args.format == 'fit':
        parser.error('--recorded-only cannot be combined with --format fit (Komoot exports FIT only for planned tours)')

    # Show kompy's warnings (e.g. a tour that failed to download) on the console.
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')

    # Any filter accepted by KomootConnector.get_tours() can be passed to download_tours().
    filters: dict[str, Any] = {}
    if args.recorded_only:
        filters['tour_type'] = TourTypes.TOUR_RECORDED
    if args.planned_only or args.format == 'fit':
        # Komoot only exports planned tours as FIT, so FIT implies planned tours.
        filters['tour_type'] = TourTypes.TOUR_PLANNED
    if args.since:
        filters['start_date'] = args.since

    try:
        with KomootConnector.from_env() as connector:
            paths = connector.download_tours(args.dest_dir, fmt=args.format, overwrite=args.overwrite, **filters)
    except DownloadError as error:
        # The other tours were saved: report the failures and the files that are there.
        print(f'{len(error.paths)} tours saved in {args.dest_dir}, {len(error.failures)} failed:')
        for tour_id, failure in error.failures.items():
            print(f'  tour {tour_id}: {failure}')
        return 1
    except KomootError as error:
        print(f'Komoot request failed: {error}')
        return 1

    print(f'{len(paths)} tours saved in {args.dest_dir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
