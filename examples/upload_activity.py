"""
Upload an activity file (.gpx, .fit or .tcx) to Komoot as a recorded tour.

The new tour is private by default. Komoot recognises a file it already has: no duplicate is created and the id of
the existing tour is printed instead.

Credentials are read from the environment: ``KOMOOT_EMAIL`` and ``KOMOOT_PASSWORD``, or ``KOMOOT_USERNAME`` and
``KOMOOT_TOKEN``.

Examples::

    python examples/upload_activity.py morning-run.gpx --sport jogging --name 'Morning run'
    python examples/upload_activity.py ride.fit --sport racebike --name 'Col du Galibier' --status friends

This script CHANGES your account: it creates a tour (use ``--dry-run`` to only check the arguments).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from kompy import KomootAPIError, KomootConnector, KomootError, PrivacyStatus, SupportedActivities


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('file', type=Path, help='a .gpx, .fit or .tcx file')
    parser.add_argument(
        '--sport',
        default=SupportedActivities.HIKING,
        help=f'Komoot sport (default: hike); e.g. {", ".join(SupportedActivities.list_all()[:6])}, ...',
    )
    parser.add_argument('--name', help='tour name (default: the file name)')
    parser.add_argument(
        '--status',
        choices=PrivacyStatus.list_all(),
        default=PrivacyStatus.PRIVATE,
        help='who can see the tour (default: private)',
    )
    parser.add_argument('--dry-run', action='store_true', help='check the arguments but do not upload')
    args = parser.parse_args(argv)

    # kompy logs a warning for sports it does not know (it sends them anyway, Komoot may have added them).
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')

    if not args.file.is_file():
        parser.error(f'{args.file} is not a file')
    name = args.name or args.file.stem
    if args.dry_run:
        print(f'Would upload {args.file} as {name!r} ({args.sport}, {args.status}).')
        return 0

    try:
        with KomootConnector.from_env() as connector:
            # upload_tour also accepts a gpxpy GPX object or a fit_tool FitFile instead of a path.
            result = connector.upload_tour(args.file, args.sport, name, status=args.status)
    except KomootAPIError as error:  # Komoot rejected the upload (e.g. an invalid file)
        print(f'Komoot rejected the upload: {error}')
        if error.body:
            print(f'Response: {error.body}')
        return 1
    except KomootError as error:
        print(f'Upload failed: {error}')
        return 1

    if result.created:
        print(f'Uploaded: https://www.komoot.com/tour/{result.tour_id}')
    else:
        print(f'Komoot already had this activity: https://www.komoot.com/tour/{result.tour_id}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
