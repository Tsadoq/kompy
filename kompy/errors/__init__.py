"""
Errors kept at their historical import paths.

New code can import them from here, or catch them through :class:`kompy.exceptions.KomootError`.
"""

from kompy.errors.initialisation_errors import NotEmailError
from kompy.errors.privacy_errors import PrivacyError

__all__ = ['NotEmailError', 'PrivacyError']
