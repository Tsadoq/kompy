"""
Summarise your recorded activities by sport: number of tours, distance, elevation gain and time in motion.

Tours are fetched lazily, one page at a time, with ``KomootConnector.iter_tours()``, so even large accounts use
little memory.

Credentials are read from the environment: ``KOMOOT_EMAIL`` and ``KOMOOT_PASSWORD``, or ``KOMOOT_USERNAME`` and
``KOMOOT_TOKEN``.

Examples::

    python examples/stats_by_sport.py              # all time
    python examples/stats_by_sport.py --year 2025

This script only reads data; it never changes anything on your account.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from kompy import KomootConnector, KomootError, Tour, TourTypes


@dataclass
class SportTotals:
    """Running totals for one sport."""

    tours: int = 0
    distance_m: float = 0.0
    elevation_up_m: float = 0.0
    in_motion_s: int = 0

    def add(self, tour: Tour) -> None:
        # Optional fields are None when Komoot does not report them, hence the `or 0`.
        self.tours += 1
        self.distance_m += tour.distance or 0
        self.elevation_up_m += tour.elevation_up or 0
        self.in_motion_s += tour.time_in_motion or tour.total_duration or 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--year', type=int, help='only count tours of this year')
    args = parser.parse_args(argv)

    # Komoot filters by date on the server. A bare date means midnight, so the range ends on the last second of
    # the year. (Naive dates and datetimes are taken to be in UTC.)
    start = datetime(args.year, 1, 1, tzinfo=UTC) if args.year else None
    end = datetime(args.year, 12, 31, 23, 59, 59, tzinfo=UTC) if args.year else None

    totals: defaultdict[str, SportTotals] = defaultdict(SportTotals)
    try:
        with KomootConnector.from_env() as connector:
            for tour in connector.iter_tours(tour_type=TourTypes.TOUR_RECORDED, start_date=start, end_date=end):
                # Sports kompy does not know yet are kept as plain strings, so nothing is lost.
                totals[str(tour.sport or 'unknown')].add(tour)
    except KomootError as error:
        print(f'Komoot request failed: {error}')
        return 1

    if not totals:
        print('No recorded tours found.')
        return 0

    print(f'{"sport":<18}{"tours":>7}{"km":>10}{"climb m":>10}{"in motion":>14}')
    for sport, sport_totals in sorted(totals.items(), key=lambda item: item[1].distance_m, reverse=True):
        print(
            f'{sport:<18}{sport_totals.tours:>7}{sport_totals.distance_m / 1000:>10.1f}'
            f'{sport_totals.elevation_up_m:>10.0f}{timedelta(seconds=sport_totals.in_motion_s)!s:>14}'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
