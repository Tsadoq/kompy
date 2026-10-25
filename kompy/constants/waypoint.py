"""Deprecated location of :class:`kompy.Waypoint`, kept so that old imports keep working."""

from __future__ import annotations

import warnings
from typing import Any

__all__: list[str] = []


def __getattr__(name: str) -> Any:
    """
    Resolve ``kompy.constants.waypoint.Waypoint``, which moved to :mod:`kompy.waypoint`, with a deprecation warning.

    :param name: Name of the attribute being looked up.
    :return: The :class:`kompy.Waypoint` class.
    :raises AttributeError: For any other unknown attribute.
    """
    if name == 'Waypoint':
        from kompy.waypoint import Waypoint  # noqa: PLC0415 - imported lazily to avoid a circular import

        warnings.warn(
            'kompy.constants.waypoint.Waypoint is deprecated; import Waypoint from kompy instead.',
            DeprecationWarning,
            stacklevel=2,
        )
        return Waypoint
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
