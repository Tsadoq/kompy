"""Geographic coordinates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self

from kompy._parsing import optional_float

__all__ = ['Coordinate']


@dataclass
class Coordinate:
    """
    A point on the earth, optionally with altitude and a time offset.

    Latitude and longitude are validated. Altitude is not: it is measured data (often from a barometer or GPS) and
    implausible readings are common in recorded tracks, so rejecting them would make whole tours unreadable.

    :param lat: Latitude in degrees, between -90 and 90.
    :param lon: Longitude in degrees, between -180 and 180.
    :param alt: Altitude in meters (optional).
    :param time: Time offset (optional), must be 0 or greater. For tour coordinates this is the number of
        milliseconds since the start of the tour.
    :raises ValueError: If latitude, longitude or time is out of range.
    """

    lat: float
    lon: float
    alt: float | None = None
    time: float | None = None

    def __post_init__(self) -> None:
        self.validate_lat(lat=self.lat)
        self.validate_lon(lon=self.lon)
        self.validate_time(time=self.time)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """
        Build a coordinate from the API shape ``{"lat": ..., "lng": ..., "alt": ..., "t": ...}``.

        :param data: The coordinate payload; ``alt`` and ``t`` are optional.
        :return: The parsed coordinate.
        :raises KeyError: If ``lat`` or ``lng`` is missing.
        :raises ValueError: If a value is out of range.
        """
        return cls(
            lat=float(data['lat']),
            lon=float(data['lng']),
            alt=optional_float(data.get('alt')),
            time=optional_float(data.get('t')),
        )

    def to_dict(self) -> dict[str, float]:
        """
        Convert the coordinate back to the API shape.

        :return: A dictionary with ``lat`` and ``lng`` plus ``alt`` and ``t`` when they are set.
        """
        data = {'lat': self.lat, 'lng': self.lon}
        if self.alt is not None:
            data['alt'] = self.alt
        if self.time is not None:
            data['t'] = self.time
        return data

    @staticmethod
    def validate_lat(lat: float) -> None:
        """
        Check that a latitude is within [-90, 90].

        :param lat: The latitude to check.
        :raises ValueError: If the latitude is out of range.
        """
        if not -90 <= lat <= 90:
            raise ValueError(f'Invalid latitude provided: {lat}. Please provide a latitude between -90 and 90.')

    @staticmethod
    def validate_lon(lon: float) -> None:
        """
        Check that a longitude is within [-180, 180].

        :param lon: The longitude to check.
        :raises ValueError: If the longitude is out of range.
        """
        if not -180 <= lon <= 180:
            raise ValueError(f'Invalid longitude provided: {lon}. Please provide a longitude between -180 and 180.')

    @staticmethod
    def validate_alt(alt: float | None) -> None:
        """
        Kept for backward compatibility: altitude is no longer validated, so this never raises.

        :param alt: The altitude in meters.
        """

    @staticmethod
    def validate_time(time: float | None) -> None:
        """
        Check that a time offset is not negative.

        :param time: The time offset, or ``None``.
        :raises ValueError: If the time is negative.
        """
        if time is not None and time < 0:
            raise ValueError(f'Invalid time provided: {time}. Please provide a time equal or above 0.')
