"""
Endpoints of the Komoot API.

The templates contain ``{placeholders}`` for path segments. Fill them with ``kompy._http.build_url`` (which
URL-quotes every value) rather than with :meth:`str.format`.
"""

from __future__ import annotations

from typing import Final

__all__ = ['KomootUrl']

_API: Final[str] = 'https://api.komoot.de'


class KomootUrl:
    """URL templates of the Komoot API endpoints used by kompy."""

    API_BASE_URL: Final[str] = _API
    """Root of the Komoot API."""

    USER_LOGIN_URL: Final[str] = f'{_API}/v006/account/email/{{email_address}}/'
    """Login with email and password; answers with the username and the API token."""

    LIST_TOURS_URL: Final[str] = f'{_API}/v007/users/{{user_identifier}}/tours/'
    """Paginated list of a user's tours."""

    TOUR_URL: Final[str] = f'{_API}/v007/tours/{{tour_identifier}}'
    """A single tour (append ``.gpx`` or ``.fit`` for the exported file)."""

    TOUR_COORDINATES_URL: Final[str] = f'{_API}/v007/tours/{{tour_identifier}}/coordinates'
    """All coordinates of a tour."""

    TOUR_COVER_IMAGES_URL: Final[str] = f'{_API}/v007/tours/{{tour_identifier}}/cover_images/'
    """Paginated list of a tour's cover images."""

    UPLOAD_TOUR_URL: Final[str] = f'{_API}/v007/tours/'
    """Upload a GPX, FIT or TCX file (the format goes in the ``data_type`` query parameter), or save a routed tour."""

    ROUTING_URL: Final[str] = 'https://www.komoot.com/api/routing/tour'
    """Komoot's route planner: routes a tour between waypoints (served by the website, not by ``api.komoot.de``)."""

    USER_URL: Final[str] = f'{_API}/v007/users/{{user_identifier}}/'
    """Full profile of the logged-in user."""

    USER_PROFILE_URL: Final[str] = f'{_API}/v007/users/{{user_identifier}}/profile_embedded'
    """Short public profile of any user."""

    USER_HIGHLIGHTS_URL: Final[str] = f'{_API}/v007/users/{{user_identifier}}/highlights/'
    """Paginated list of the highlights a user recommended."""

    HIGHLIGHT_URL: Final[str] = f'{_API}/v007/highlights/{{highlight_identifier}}'
    """A single highlight."""
