from typing import Final


class KomootUrl:
    USER_LOGIN_URL: Final[str] = 'https://api.komoot.de/v006/account/email/{email_address}/'
    LIST_TOURS_URL: Final[str] = 'https://api.komoot.de/v007/users/{user_identifier}/tours/'
    DOWNLOAD_TOUR_URL: Final[str] = 'https://api.komoot.de/v007/tours/{tour_identifier}'
    UPLOAD_TOUR_URL: Final[str] = 'https://api.komoot.de/v007/tours/?data_type={object_type}'
