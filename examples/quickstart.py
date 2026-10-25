"""
Quickstart: log in, show who you are, list your latest tours and look at one of them in detail.

Credentials are read from the environment, never from the code:

* ``KOMOOT_EMAIL`` and ``KOMOOT_PASSWORD``, or
* ``KOMOOT_USERNAME`` and ``KOMOOT_TOKEN`` (see ``kompy token`` or ``connector.token``).

Run it with::

    export KOMOOT_EMAIL='you@example.com'
    export KOMOOT_PASSWORD='...'
    python examples/quickstart.py            # the 5 latest tours
    python examples/quickstart.py --limit 20

This script only reads data; it never changes anything on your account.
"""

from __future__ import annotations

import argparse
import logging

from kompy import KomootConnector, KomootError, TourSort, TourSortField


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--limit', type=int, default=5, help='number of tours to list (default: 5)')
    parser.add_argument('-v', '--verbose', action='store_true', help="show kompy's log messages")
    args = parser.parse_args(argv)

    # kompy never configures logging itself; opt in to see what it does (requests, retries, skipped tours).
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING)

    try:
        # The connector holds an HTTP session: the `with` block closes it at the end.
        with KomootConnector.from_env() as connector:
            user = connector.get_user()
            print(f'Logged in as {user.display_name} (username {user.username})\n')

            # `limit` is the total number of tours to return; kompy fetches as many pages as needed.
            tours = connector.get_tours(limit=args.limit, sort_field=TourSortField.DATE, sort=TourSort.DESCENDING)
            if not tours:
                print('No tours yet.')
                return 0

            print(f'Your {len(tours)} latest tours:')
            for tour in tours:
                day = tour.start_date.date() if tour.start_date else '?'
                km = f'{tour.distance_km:.1f} km' if tour.distance_km is not None else '? km'
                kind = 'recorded' if tour.is_recorded else 'planned'
                print(f'  {day}  {tour.sport!s:<16} {km:>9}  {kind:<8}  {tour.name}')

            # Fetch the latest tour again, this time with its coordinates, surfaces and way types embedded.
            latest = connector.get_tour_by_id(tours[0].id, embedded=True)
            print(f'\nLatest tour: {latest.name}')
            print(f'  link:           {latest.url}')
            print(f'  duration:       {latest.duration_timedelta}')
            print(f'  in motion:      {latest.time_in_motion_timedelta}')
            print(f'  elevation:      +{latest.elevation_up or 0:.0f} m / -{latest.elevation_down or 0:.0f} m')
            print(f'  visibility:     {latest.status}')
            print(f'  track points:   {len(latest.coordinates)}')
            if latest.coordinates:
                first, last = latest.coordinates[0], latest.coordinates[-1]
                print(f'  starts at:      {first.lat:.5f}, {first.lon:.5f}')
                print(f'  ends at:        {last.lat:.5f}, {last.lon:.5f}')
    except KomootError as error:  # every error kompy raises derives from KomootError
        print(f'Komoot request failed: {error}')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
