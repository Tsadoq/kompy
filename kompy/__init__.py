"""
A typed Python client for [Komoot](https://www.komoot.com): list, download, upload, edit and delete your tours.

kompy turns Komoot's API into Python methods and objects. It can list and search tours, export them as GPX or FIT
files (one at a time or a whole-account backup), upload activities, rename them or change their visibility,
delete them, and read user profiles and highlights. It takes care of pagination, timeouts, retries and typed
errors, and includes a command-line tool (run `kompy --help`).

.. warning::
    kompy is an unofficial project, not affiliated with or endorsed by Komoot GmbH. It uses the same undocumented
    API as the Komoot apps, which **may change or break at any time**. Use it only with your own account and
    follow Komoot's terms of service.

## Installation

```bash
pip install kompy            # or: uv add kompy
pip install "kompy[images]"  # with Pillow, for KomootImage.load_image()
```

kompy needs Python 3.11 or newer.

## Quickstart

```python
from kompy import KomootConnector, TourTypes

# Reads KOMOOT_EMAIL and KOMOOT_PASSWORD (or KOMOOT_USERNAME and KOMOOT_TOKEN) from the environment.
with KomootConnector.from_env() as connector:
    tours = connector.get_tours(limit=10, tour_type=TourTypes.TOUR_RECORDED)
    for tour in tours:
        print(tour.start_date, tour.sport, tour.distance_km, tour.name)

    if tours:
        gpx = connector.get_tour_gpx(tours[0])  # a gpxpy GPX object
        connector.download_tour(tours[0], 'komoot-backup/')  # saved as komoot-backup/<id>_<name>.gpx

    # To back up every tour of the account (one request per tour), use connector.download_tours('komoot-backup').
```

You can also log in explicitly with `KomootConnector(email=..., password=...)`, or reuse a token you saved
earlier with `KomootConnector.from_token(username, token)`. The token is equivalent to your password, so keep it
just as secret.

## Where to go next

- `KomootConnector`: every API call, including authentication, listing, downloads, uploads, edits, users and
  highlights.
- `Tour`, `Coordinate`, `User`, `Highlight` and `KomootImage`: the data models. Parsing is lenient: missing
  optional fields are `None`, and values kompy does not know yet are kept as plain strings.
- `kompy.exceptions`: every error derives from `KomootError`.
- `kompy.constants`: string enums such as `SupportedActivities`, `PrivacyStatus` and `TourTypes`.
- The command-line tool: run `kompy --help`, or see the README.

kompy logs on the `'kompy'` logger and never configures logging itself: call
`logging.basicConfig(level=logging.INFO)` to see its messages.

Links: [README and full guide](https://github.com/Tsadoq/kompy#readme) ·
[changelog](https://github.com/Tsadoq/kompy/blob/main/CHANGELOG.md) ·
[examples](https://github.com/Tsadoq/kompy/tree/main/examples) ·
[source code](https://github.com/Tsadoq/kompy) · [PyPI](https://pypi.org/project/kompy/) ·
[issues](https://github.com/Tsadoq/kompy/issues)
"""

__docformat__ = 'restructuredtext'
__version__ = '0.1.0'

import logging

from kompy import constants, exceptions
from kompy.authentication import Authentication
from kompy.constants import (
    DifficultyGrade,
    PossibleWayType,
    PrivacyStatus,
    SegmentType,
    SmartTourTypes,
    SupportedActivities,
    SurfaceType,
    TourObjectTypes,
    TourSort,
    TourSortField,
    TourTypes,
)
from kompy.coordinate import Coordinate
from kompy.difficulty import Difficulty
from kompy.errors import NotEmailError, PrivacyError
from kompy.exceptions import (
    AuthenticationError,
    DownloadError,
    KomootAPIError,
    KomootConnectionError,
    KomootError,
    KomootResponseError,
    KomootTimeoutError,
    NotFoundError,
    RateLimitError,
    ServerError,
    UnsupportedFormatError,
    UploadStatusError,
)
from kompy.highlight import Highlight
from kompy.image import KomootImage
from kompy.komoot_connector import KomootConnector, UploadResult
from kompy.segment import AnnotatedSegment, Segment, SegmentInformation
from kompy.surface import Surface
from kompy.tour import Tour, TourInformation, TourSummary
from kompy.user import User
from kompy.way_type import WayType
from kompy.waypoint import Waypoint

__all__ = [
    'AnnotatedSegment',
    'Authentication',
    'AuthenticationError',
    'Coordinate',
    'Difficulty',
    'DifficultyGrade',
    'DownloadError',
    'Highlight',
    'KomootAPIError',
    'KomootConnectionError',
    'KomootConnector',
    'KomootError',
    'KomootImage',
    'KomootResponseError',
    'KomootTimeoutError',
    'NotEmailError',
    'NotFoundError',
    'PossibleWayType',
    'PrivacyError',
    'PrivacyStatus',
    'RateLimitError',
    'Segment',
    'SegmentInformation',
    'SegmentType',
    'ServerError',
    'SmartTourTypes',
    'SupportedActivities',
    'Surface',
    'SurfaceType',
    'Tour',
    'TourInformation',
    'TourObjectTypes',
    'TourSort',
    'TourSortField',
    'TourSummary',
    'TourTypes',
    'UnsupportedFormatError',
    'UploadResult',
    'UploadStatusError',
    'User',
    'WayType',
    'Waypoint',
    '__version__',
    'constants',
    'exceptions',
]

logging.getLogger(__name__).addHandler(logging.NullHandler())
