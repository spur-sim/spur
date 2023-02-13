"""Spur-specific exceptions."""


class SpurError(Exception):
    """Generic base exception for Spur errors."""


class NotPositiveError(SpurError):
    """Parameter or value must be strictly positive."""


class NotAProbabilityError(SpurError):
    """Value must be in the range [0, 1]"""


class NotUniqueIDError(SpurError):
    """Something is not unique that should be"""


class InputMismatchError(SpurError):
    """Input files are not consistent with each other or within themselves"""
