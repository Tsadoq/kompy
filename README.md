# Kompy

![example workflow](https://github.com/tsadoq/kompy/actions/workflows/python-app.yml/badge.svg)

## Overview

Kompy is a wrapper for [Komoot APIs](https://static.komoot.de/doc/external-api/v007/index.html) that allows you to
download and upload your activities from Komoot.

## Features

- **Download Activities from Komoot**: Download your activities from Komoot to GPX, FIT or Custom Object format.
- **Upload Activities to Komoot**: Upload your activities to Komoot from GPX, FIT files.
- **Download Tours from Komoot**: Download your tours from Komoot
-

## Installation

To get started with the Kompy, follow these steps:

1. Ensure you have Python installed on your system. This app is compatible with Python 3.11 and above.

2. pip the package:

    ```bash
    pip install kompy
    ```
3. Import the package to your project:
    ```python
   import kompy as kp
    ```

## Usage

For a more detailed usage example, please
check [this notebook](https://github.com/Tsadoq/kompy/blob/main/examples/run_kompy.ipynb).

The most basic usage is:

1. Create a connector:
    ```python
   from kompy import KomootConnector
   connector = KomootConnector(password=..., email=...)
    ```
2. Fetch your activities:
    ```python
   tours_list = connector.get_tours(user_identifier=None)
    ```

## Run the tests

To run the tests (locally), run:

```bash
  pytest .
```

Currently you need to log in to run the tests. To do so you need to set some environment variables:

```bash
  export KOMOOT_EMAIL=<your email>
  export KOMOOT_PASSWORD=<your password>
```

## Contributing

Contributions to Kompy are welcome! If you have a suggestion that would make this app better, please fork the repo
and create a pull request. You can also simply open an issue with the tag "enhancement".

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Acknowledgements

- [Requests](https://docs.python-requests.org/en/latest/)
- [Python Imaging Library (PIL)](https://python-pillow.org/)
- [gpxpy](https://github.com/tkrajina/gpxpy)
- [FIT](https://pypi.org/project/fit-tool/)