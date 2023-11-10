from typing import Optional

from pydantic import BaseModel, field_validator


class Coordinate(BaseModel):
    """
    Coordinate object.

    :param lat: latitude
    :param lon: longitude
    :param alt: altitude (in meters), if not provided, set to none
    :param time: time, if not provided, set to none
    """
    lat: float
    lon: float
    alt: Optional[float]
    time: Optional[float]

    @field_validator('lat')
    def check_lat(cls, lat):
        if not -90 <= lat <= 90:
            raise ValueError(f'Invalid latitude provided: {lat}. Please provide a latitude between -90 and 90.')

    @field_validator('lon')
    def check_lon(cls, lon):
        if not -180 <= lon <= 180:
            raise ValueError(f'Invalid longitude provided: {lon}. Please provide a longitude between -180 and 180.')

    @field_validator('alt')
    def check_alt(cls, alt):
        if not -10000 <= alt <= 10000 and not alt:
            raise ValueError(f'Invalid altitude provided: {alt}. Please provide an altitude between -10000 and 10000.')

    @field_validator('time')
    def check_time(cls, time):
        if not 0 <= time and not time:
            raise ValueError(f'Invalid time provided: {time}. Please provide a time equal or above 0.')
