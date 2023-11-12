from typing import Optional


class Coordinate:
    def __init__(
        self,
        lat: float,
        lon: float,
        alt: Optional[float] = None,
        time: Optional[float] = None,
    ):
        """
        Initialize the Coordinate object.
        :param lat: Latitude, must be between -90 and 90.
        :param lon: Longitude, must be between -180 and 180.
        :param alt: Altitude in meters (optional), must be between -10000 and 10000 if provided.
        :param time: Time (optional), must be equal or above 0 if provided.
        """
        self.validate_lat(lat=lat)
        self.validate_lon(lon=lon)
        self.validate_alt(alt=alt)
        self.validate_time(time=time)

        self.lat = lat
        self.lon = lon
        self.alt = alt
        self.time = time

    @staticmethod
    def validate_lat(lat: float):
        if not -90 <= lat <= 90:
            raise ValueError(f'Invalid latitude provided: {lat}. Please provide a latitude between -90 and 90.')

    @staticmethod
    def validate_lon(lon: float):
        if not -180 <= lon <= 180:
            raise ValueError(f'Invalid longitude provided: {lon}. Please provide a longitude between -180 and 180.')

    @staticmethod
    def validate_alt(alt: float):
        if alt is not None and not -10000 <= alt <= 10000:
            raise ValueError(f'Invalid altitude provided: {alt}. Please provide an altitude between -10000 and 10000.')

    @staticmethod
    def validate_time(time: float):
        if time is not None and time < 0:
            raise ValueError(f'Invalid time provided: {time}. Please provide a time equal or above 0.')
