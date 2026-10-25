"""Access to the anonymized Komoot API payloads stored in ``tests/resources/api``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

API_FIXTURES = Path(__file__).parent.parent / 'resources' / 'api'


def read_api_fixture(name: str) -> Any:
    """
    Load an anonymized API payload.

    :param name: File name without the ``.json`` suffix.
    :return: The decoded JSON payload (a fresh copy on every call).
    """
    return json.loads((API_FIXTURES / f'{name}.json').read_text(encoding='utf-8'))
