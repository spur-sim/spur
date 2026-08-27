import logging

from .model import Model


# Library code must not attach handlers or write files on import - that is
# the embedding application's decision. This NullHandler just silences
# Python's "no handlers found" warning when nothing is configured.
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
