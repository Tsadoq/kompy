# kompy

[![CI](https://github.com/Tsadoq/kompy/actions/workflows/ci.yml/badge.svg)](https://github.com/Tsadoq/kompy/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/kompy)](https://pypi.org/project/kompy/)
[![Python versions](https://img.shields.io/pypi/pyversions/kompy)](https://pypi.org/project/kompy/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/Tsadoq/kompy/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-pdoc-informational)](https://tsadoq.github.io/kompy/)

**kompy** is a typed Python client for [Komoot](https://www.komoot.com). Use it to list and search your tours,
download them as GPX or FIT files (one at a time or as a whole-account backup), upload activities, rename them,
change their visibility, delete them, and read user profiles and highlights. Results come back as Python objects
(`Tour`, `Coordinate`, `User`, `Highlight`, ...) with timezone-aware dates and proper units. kompy also handles
pagination, timeouts, retries and typed errors, and includes a small `kompy` command-line tool.

> **Unofficial project.** kompy is not affiliated with, endorsed by or supported by Komoot GmbH. It uses the
> same undocumented API as the Komoot apps (`api.komoot.de`, with basic authentication). Komoot's
> [public API](https://static.komoot.de/doc/external-api/v007/index.html) is for partners only and documents
> some of these endpoints, but the ones used to edit, delete and upload tours are not documented at all.
> **The API may change or break at any time**, without notice. Use kompy only with your own account, keep the
> request rate reasonable, and follow [Komoot's terms of service](https://www.komoot.com/terms-of-service).

**Contents:** [Installation](#installation) · [Quickstart](#quickstart) · [Authentication](#authentication) ·
[Usage](#usage) · [Models](#models) · [Errors](#error-handling) · [Command line](#command-line) ·
[Logging](#logging) · [Upgrading from 0.0.x](#upgrading-from-00x) · [Contributing](#contributing)

## Installation

kompy needs Python 3.11 or newer.

```bash
pip install kompy
# or
uv add kompy
```

Pillow is optional. You only need it to download images as `PIL.Image` objects with `KomootImage.load_image()`.
To install it with kompy:

```bash
pip install "kompy[images]"
```

## Quickstart

```python
from kompy import KomootConnector

with KomootConnector(email='you@example.com', password='...') as connector:
    for tour in connector.get_tours(limit=5, sort_field='date', sort='desc'):
        km = f'{tour.distance_km:.1f} km' if tour.distance_km is not None else '? km'
        print(tour.start_date, tour.sport, km, tour.name)
```

The [`examples/`](https://github.com/Tsadoq/kompy/tree/main/examples) folder has runnable scripts:
[quickstart](https://github.com/Tsadoq/kompy/blob/main/examples/quickstart.py),
[back up every tour](https://github.com/Tsadoq/kompy/blob/main/examples/export_all_tours.py),
[upload an activity](https://github.com/Tsadoq/kompy/blob/main/examples/upload_activity.py) and
[statistics by sport](https://github.com/Tsadoq/kompy/blob/main/examples/stats_by_sport.py).

## Authentication

Komoot has two kinds of credentials:

1. **Your email address and password**, which are used once, to log in.
2. **Your username and an API token**, which the login returns. Every later request uses them, so kompy does not
   send your password again after the login.

### Email and password

```python
from kompy import KomootConnector

connector = KomootConnector(email='you@example.com', password='...')
print(connector.username)  # your Komoot username (usually a number)
connector.close()
```

The connector holds an HTTP session. Close it with `close()`, or use it as a context manager, which closes it for
you:

```python
with KomootConnector(email='you@example.com', password='...') as connector:
    ...
```

### Environment variables

Keep credentials out of your code with `KomootConnector.from_env()`:

```bash
export KOMOOT_EMAIL='you@example.com'
export KOMOOT_PASSWORD='...'
```

```python
with KomootConnector.from_env() as connector:
    ...
```

`from_env()` uses `KOMOOT_USERNAME` and `KOMOOT_TOKEN` when both are set (see the next section). Otherwise it uses
`KOMOOT_EMAIL` and `KOMOOT_PASSWORD`. If neither pair is set, it raises `ValueError`. Pass `prefix='MY_APP_'` to
read `MY_APP_EMAIL` and so on instead.

### Token authentication

Once you have logged in, you can store the token and connect with it later. This way your password does not have
to be stored anywhere:

```python
connector = KomootConnector(email='you@example.com', password='...')
username, token = connector.username, connector.token  # store these somewhere safe

# later, without the password and without a login request:
connector = KomootConnector.from_token(username, token)
connector = KomootConnector.from_token(username, token, validate=True)  # check the token right away
```

The CLI can print these values for you: run `kompy token`.

> **The token is equivalent to your password: keep it just as secret.** Anyone who has it can read, change and
> delete your tours. In our tests it is long-lived: every login returns the same token, and it stays valid when you
> log in again. Changing your Komoot password probably revokes it, but this has not been verified. When Komoot
> rejects a token, kompy raises `AuthenticationError` and you need to log in again with your email and password.

Komoot's official [OAuth 2 API](https://static.komoot.de/doc/auth/oauth2.html) needs a partner contract with
Komoot, so kompy does not support it.

### Connection options

Every constructor (`KomootConnector(...)`, `from_env()` and `from_token()`) accepts these keyword-only options:

| Option | Default | Meaning |
| --- | --- | --- |
| `timeout` | `(5, 30)` | Timeout in seconds of each request: one number, or a `(connect, read)` pair. |
| `max_retries` | `3` | How many times a read-only request (GET) is retried on connection errors and on HTTP 429/502/503/504, with exponential backoff. kompy waits for a `Retry-After` of up to 60 seconds; when Komoot asks for a longer pause, kompy raises `RateLimitError` (with `retry_after`) right away instead of blocking. Uploads, edits and deletes are never retried. `0` disables retries. |
| `session` | `None` | Your own `requests.Session`, for example with proxies set. kompy does not close it. |

```python
import requests

session = requests.Session()
session.proxies = {'https': 'http://proxy.example.com:3128'}
connector = KomootConnector.from_env(timeout=60, max_retries=5, session=session)
```

## Usage

The examples below assume a logged-in `connector`. Constants can be given as enum members
(`SupportedActivities.HIKING`) or as plain strings (`'hike'`); both work the same way.

### Listing tours: `get_tours` and `iter_tours`

```python
from kompy import PrivacyStatus, SupportedActivities, TourSort, TourSortField, TourTypes

tours = connector.get_tours()  # all your tours (planned and recorded, of every visibility)

recent_hikes = connector.get_tours(
    limit=20,  # the total number of tours to return; kompy fetches as many pages as needed
    tour_type=TourTypes.TOUR_RECORDED,
    sport_types=[SupportedActivities.HIKING, SupportedActivities.MOUNTAINEERING],
    start_date='2024-01-01',  # a str, date or datetime; naive values are taken to be in UTC
    sort_field=TourSortField.DATE,
    sort=TourSort.DESCENDING,
)

private_tours = connector.get_tours(status=PrivacyStatus.PRIVATE)
named = connector.get_tours(tour_name='dolomites')  # the name contains this text (case-insensitive)
nearby = connector.get_tours(center='46.5547,11.8735', max_distance=20_000)  # within 20 km of a point
others = connector.get_tours(user_identifier='987654321')  # another user's public tours
```

All parameters are optional:

| Parameter | Meaning |
| --- | --- |
| `limit` | The maximum number of tours to return (default: all). |
| `user_identifier` | Whose tours to list (default: yours). For other users only public tours are available; asking for other statuses raises `PrivacyError`. |
| `page`, `page_size` | Fetch only page `page` (counted from 0). Each page holds `page_size` tours, or `limit` tours if `page_size` is not given (100 if neither is), so `page=2, limit=10` is tours 20 to 29. A `status` filter is applied to the tours of that page afterwards, so the page can hold fewer tours. |
| `status` | `PrivacyStatus.PUBLIC`, `FRIENDS` or `PRIVATE` (default: every status). Komoot ignores this filter for your own tours, so kompy filters them itself; it then lists all your tours in pages of 1000. |
| `tour_type` | `TourTypes.TOUR_PLANNED` or `TourTypes.TOUR_RECORDED`. |
| `sport_types` | A list of sports (see `SupportedActivities`). |
| `start_date`, `end_date` | Date range. |
| `tour_name` | Text that must appear in the name. |
| `center`, `max_distance` | A `'lat,lng'` point and a distance in meters. Always give them together. |
| `sort_field`, `sort` | A `TourSortField` (`'date'`, `'name'`, `'duration'`, `'elevation'`, `'proximity'`) and a `TourSort` (`'asc'` or `'desc'`). `'proximity'` requires `center`. |
| `only_unlocked` | Only return unlocked tours. |

`iter_tours()` takes the same arguments but returns a lazy iterator. It requests the next page only when you need
it, so you can stop early and memory use stays low on large accounts:

```python
for tour in connector.iter_tours(tour_type=TourTypes.TOUR_RECORDED):
    if tour.distance_km and tour.distance_km > 100:
        print('First ride over 100 km:', tour.name, tour.url)
        break
```

### One tour: `get_tour_by_id`

```python
tour = connector.get_tour_by_id(1234567890)
print(tour)  # Tour(id=1234567890, name='Sample name', sport='hike', date='2024-05-01')

# Embed coordinates, way types, surfaces and directions in the same request:
tour = connector.get_tour_by_id(1234567890, embedded=True)
print(len(tour.coordinates), tour.way_type_segments[:3], tour.surface_segments[:3])

tour = connector.get_tour_by_id(1234567890, embedded=['coordinates'])  # only what you need

# A share token gives access to a tour that someone shared with you:
shared = connector.get_tour_by_id(1234567890, share_token='abc123')
```

`get_tour_by_id(tour_id, object_type='gpx')` and `object_type='fit'` return the same objects as `get_tour_gpx()`
and `get_tour_fit()` below.

### GPX and FIT: `get_tour_gpx` and `get_tour_fit`

```python
gpx = connector.get_tour_gpx(tour)  # a gpxpy.gpx.GPX object, also stored in tour.gpx_track
print(gpx.length_3d(), gpx.get_uphill_downhill())
xml = gpx.to_xml()

fit = connector.get_tour_fit(planned_tour_id)  # a fit_tool FitFile; planned tours only
```

Every method that takes a tour (`get_tour_by_id`, `change_tour`, `delete_tour`, the downloads, ...) accepts either a
`Tour` or its id. Komoot provides FIT files only for planned tours.
For a recorded tour, `get_tour_fit()` raises `UnsupportedFormatError`.

### Coordinates and photos: `get_tour_coordinates` and `get_tour_cover_images`

```python
coordinates = connector.get_tour_coordinates(tour)  # also stored in tour.coordinates
first = coordinates[0]
print(first.lat, first.lon, first.alt, first.time)  # time is milliseconds since the start of the tour

for image in connector.get_tour_cover_images(tour):
    print(image.url_for(width=1200, height=800, crop=True))  # fill in the size of a templated URL
    picture = image.load_image(width=1200)  # a PIL.Image.Image, or None; needs kompy[images]
```

### Saving files: `download_tour` and `download_tours`

`download_tour()` saves the GPX or FIT file exactly as Komoot sends it:

```python
from pathlib import Path

path = connector.download_tour(tour, 'my-tour.gpx')

exports = Path('exports')
exports.mkdir(exist_ok=True)
path = connector.download_tour(tour, exports)  # an existing folder: exports/<id>_<name>.gpx
path = connector.download_tour(planned_tour_id, exports, fmt='fit')  # exports/<id>.fit
path = connector.download_tour(tour, 'new-folder/')  # a trailing slash: the folder is created
```

`download_tours()` saves many tours into a folder, for example to back up your account. It takes the filters of
`get_tours()`. Files that already exist are skipped (unless `overwrite=True`), so you can resume an interrupted
backup by running it again. A tour counts as present under either file name, `<id>_<name>.gpx` or `<id>.gpx`. If a tour fails, kompy carries on with the others, then raises a `DownloadError` that
lists the failures:

```python
from kompy import DownloadError, TourTypes

try:
    paths = connector.download_tours('komoot-backup', fmt='gpx', tour_type=TourTypes.TOUR_RECORDED)
except DownloadError as error:
    paths = error.paths  # the files that were saved
    for tour_id, failure in error.failures.items():
        print(f'tour {tour_id} failed: {failure}')
```

### Uploading: `upload_tour`

`upload_tour()` takes a `.gpx`, `.fit` or `.tcx` file path, a `gpxpy` GPX object or a `fit_tool` FitFile:

```python
from kompy import PrivacyStatus, SupportedActivities

result = connector.upload_tour(
    'morning-run.gpx',
    activity_type=SupportedActivities.RUNNING,
    tour_name='Morning run',
    status=PrivacyStatus.PRIVATE,  # default: PrivacyStatus.FRIENDS
)
print(result.tour_id, result.created, result.status)  # created is False if Komoot already had this activity
```

Komoot's upload endpoint ignores the requested visibility and gives every new tour your account's default one. So
kompy checks the new tour and, if its visibility differs from `status`, changes it right away with `change_tour()`.
For a moment between the two requests the tour has the default visibility. If that change fails, kompy raises
`UploadStatusError`, which carries the `tour_id` so you can fix or delete the tour. Pass `status=None` to keep the
account default. When Komoot recognises the file as a duplicate (`created` is `False`), the existing tour is left
untouched: neither its name nor its visibility is changed.

`activity_type` applies to GPX uploads only: FIT and TCX files carry their own sport (change it afterwards with
`change_tour()`). For GPX and TCX files you can also pass `time_in_motion` (in seconds). FIT files carry their own.

### Editing and deleting: `change_tour` and `delete_tour`

```python
connector.change_tour(tour.id, tour_name='Sunrise hike')  # only the fields you give are changed
connector.change_tour(tour.id, activity_type=SupportedActivities.MOUNTAINEERING, status=PrivacyStatus.PUBLIC)

connector.delete_tour(tour.id)  # permanent
```

Both return `True` and raise an exception on failure (for example `NotFoundError`).

### Users and highlights: `get_user`, `get_user_highlights`, `iter_user_highlights` and `get_highlight`

```python
me = connector.get_user()  # your full profile
print(me.display_name, me.locale, me.created_at)
someone = connector.get_user('987654321')  # another user's public profile
print(someone.display_name, someone.is_premium, someone.url)

for highlight in connector.get_user_highlights(limit=10):  # the highlights you recommended
    print(highlight.name, highlight.type, highlight.sport, highlight.url)

for highlight in connector.iter_user_highlights('987654321'):  # lazy, page by page
    ...

highlight = connector.get_highlight(123456)
print(highlight.name, highlight.mid_point, highlight.front_image)
```

## Models

All models live in the `kompy` package. Parsing is lenient, so that changes to the unofficial API do not make your
data unreadable:

- Optional fields that are missing are `None`.
- Values kompy does not know yet (a new sport, surface or way type) are kept as plain strings.
- Each model keeps the original payload in `.raw`.

| Model | What it is |
| --- | --- |
| `Tour` | A planned route or a recorded activity. Main fields: `id` (an `int`), `name`, `sport`, `type`, `status`, `start_date` and `changed_at` (timezone-aware datetimes), `distance` (m), `total_duration` and `time_in_motion` (s), `elevation_up`/`elevation_down` (m), `start_point`, `creator`, `map_image`, `coordinates`, `gpx_track`. Planned tours also have `difficulty`, `summary`, `segments`, `path`, `tour_information` and `constitution`. Convenience members: `distance_km`, `duration_timedelta`, `time_in_motion_timedelta`, `is_recorded`, `is_planned`, `url` and `to_dict()`. Two tours are equal when they have the same `id`. |
| `Coordinate` | `lat`, `lon`, `alt` (m) and `time` (ms since the start of the tour). |
| `User` | `username`, `display_name`, `avatar`, `status`, `is_premium`, `locale`, `metric`, `created_at` and `url`. |
| `Highlight` | A point or segment highlight: `id`, `type`, `name`, `sport`, `start_point`/`mid_point`/`end_point`, `distance`, `elevation_up`/`elevation_down`, `front_image`, `creator` and `url`. |
| `KomootImage` | `image_url`, `templated`, `attribution`, `url_for(width, height, crop)` and `load_image()`. |
| `Difficulty`, `TourSummary`, `Surface`, `WayType`, `Segment`, `SegmentInformation`, `AnnotatedSegment`, `TourInformation`, `Waypoint` | Details of planned tours and of embedded resources. |
| `UploadResult` | The result of `upload_tour()`: `tour_id`, `created` and `raw`. It is always truthy. |

The constants in `kompy.constants` (also importable from `kompy`) are string enums: `SupportedActivities`,
`PrivacyStatus`, `TourTypes`, `TourSortField`, `TourSort`, `TourObjectTypes`, `SurfaceType`, `PossibleWayType`,
`DifficultyGrade`, `SegmentType` and `SmartTourTypes`. Each one has `list_all()`, which returns its values:

```python
from kompy import SupportedActivities

SupportedActivities.HIKING == 'hike'  # True
SupportedActivities.list_all()[:3]  # ['hike', 'mountaineering', 'mountaineering_advanced']
```

You can build models from payloads you already have with `Tour.from_dict(payload)`, `User.from_dict(...)` and so
on.

## Error handling

Every exception kompy raises on purpose derives from `kompy.KomootError`:

```text
KomootError
├── KomootConnectionError       network failure (also a ConnectionError)
│   └── KomootTimeoutError      no answer within the timeout
├── KomootAPIError              any non-2xx answer: .status_code, .url, .body, .message
│   ├── AuthenticationError     401/403: wrong credentials or revoked token (also a ConnectionError)
│   ├── NotFoundError           404 (also a ValueError)
│   ├── RateLimitError          429: .retry_after in seconds, or None
│   └── ServerError             5xx
├── KomootResponseError         a 2xx answer kompy cannot understand (also a ValueError)
├── UnsupportedFormatError      e.g. FIT for a recorded tour (also a ValueError)
├── DownloadError               download_tours: .paths and .failures
├── NotEmailError               the email address is invalid (also a ValueError)
└── PrivacyError                non-public tours of another user were requested (also a ValueError)
```

```python
from kompy import AuthenticationError, KomootError, NotFoundError, RateLimitError

try:
    tour = connector.get_tour_by_id(1234567890)
except NotFoundError:
    print('No such tour, or it is not visible to you.')
except RateLimitError as error:
    print(f'Slow down; retry in {error.retry_after} s.')
except AuthenticationError:
    print('Log in again.')
except KomootError as error:
    print(f'Komoot request failed: {error}')
```

Several exceptions also derive from the builtin `ConnectionError` or `ValueError`, because older versions raised
those. Existing `except ConnectionError:` and `except ValueError:` clauses keep working. Invalid arguments (such as
an unknown `status`) raise a plain `ValueError` or `TypeError` before any request is sent.

## Command line

Installing kompy also installs a `kompy` command (also available as `python -m kompy`). It reads the same
environment variables as `KomootConnector.from_env()`: `KOMOOT_USERNAME` and `KOMOOT_TOKEN`, or `KOMOOT_EMAIL` and
`KOMOOT_PASSWORD`. Add `--prompt-password` to any command to type the password in instead.

```bash
kompy --version
kompy whoami                                    # who you are logged in as (--json for the full profile)
kompy tours list                                # all your tours as a table
kompy tours list --type recorded --sport hike --limit 20
kompy tours list --json                         # one JSON object per line, for jq and friends
kompy tours show 1234567890                     # details of one tour (--json for the raw payload)
kompy tours download 1234567890 --dest exports  # save tours as GPX (or --format fit) into a folder
kompy tours download --all --dest backup        # back up every tour; existing files are skipped
kompy upload morning-run.gpx --sport jogging --name "Morning run" --status private
kompy token                                     # print KOMOOT_USERNAME=... and KOMOOT_TOKEN=... lines
```

`tours list` and `tours download` accept the filters `--type planned|recorded`, `--sport SPORT` (repeatable),
`--status`, `--name TEXT` and `--limit N`. Add `--debug` to any command to log every request and show
tracebacks. The exit code is `0` on success, `1` when a request or a download fails, `2` for invalid
arguments, `130` when interrupted, and `141` when the output was cut short (for example by `| head`). Run `kompy --help` or `kompy <command> --help` to see every option.

## Logging

kompy logs through the standard `logging` module, on loggers under the name `kompy`. It never configures logging
itself (the `kompy` logger only has a `NullHandler`), so by default nothing is printed. To see what kompy does,
including each request, retries and skipped tours:

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger('kompy').setLevel(logging.DEBUG)
```

Passwords and tokens are never logged, and share tokens and the login email address are replaced by `***` in log
messages and exception messages. Still check debug output for personal data (usernames, tour names) before
sharing it.

## Upgrading from 0.0.x

Version 0.1.0 is a large revamp. Most code keeps working, but read the
[changelog](https://github.com/Tsadoq/kompy/blob/main/CHANGELOG.md) before upgrading. The main
changes:

- `get_tours()` now returns **all** your tours. Before, it returned only the public ones. Use
  `status=PrivacyStatus.PUBLIC` to get the old behaviour.
- `limit` is now the total number of tours across all pages, and `page` is no longer ignored.
- `upload_tour()` returns an `UploadResult` instead of `True`.
- `upload_tour()`, `change_tour()` and `delete_tour()` raise exceptions instead of returning `False`.
- Pillow is now optional: install `kompy[images]` if you call `KomootImage.load_image()`.
- `Tour.generate_coordinates()` and `Tour.generate_gpx_track()` are deprecated. Use
  `connector.get_tour_coordinates(tour)` and `connector.get_tour_gpx(tour)`.

## Contributing

Contributions are welcome. [CONTRIBUTING.md](https://github.com/Tsadoq/kompy/blob/main/CONTRIBUTING.md) explains
how to set up the development environment (with [uv](https://docs.astral.sh/uv/)), run the tests and linters, and
make a release. To report a security problem, follow
[SECURITY.md](https://github.com/Tsadoq/kompy/blob/main/SECURITY.md).

## License

kompy is released under the [MIT License](https://github.com/Tsadoq/kompy/blob/main/LICENSE).

It is built on [Requests](https://requests.readthedocs.io/), [gpxpy](https://github.com/tkrajina/gpxpy),
[fit-tool](https://pypi.org/project/fit-tool/), [python-dateutil](https://github.com/dateutil/dateutil) and,
optionally, [Pillow](https://python-pillow.org/).
