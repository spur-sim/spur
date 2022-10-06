import os
import logging

from .model import Model


# Create a logger for the module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Set up file output and formatting
fileFormatter = logging.Formatter(
    "{asctime} {name:25s} {levelname:8s} {message}", style="{"
)

# Set up info logging to spur.log
try:
    dh = logging.FileHandler("log/debug.log", mode="w")
except FileNotFoundError:
    os.mkdir("log")
    dh = logging.FileHandler("log/debug.log", mode="w")

dh.setLevel(logging.DEBUG)
dh.setFormatter(fileFormatter)
logger.addHandler(dh)

# Set up info logging to spur.log
ih = logging.FileHandler("log/spur.log", mode="w")
ih.setLevel(logging.INFO)
ih.setFormatter(fileFormatter)
logger.addHandler(ih)

# Set up logging of errors to a separate file
eh = logging.FileHandler("log/error.log", mode="w")
eh.setLevel(logging.ERROR)
eh.setFormatter(fileFormatter)
logger.addHandler(eh)

# Set up stout output and formatting
# sh = logging.StreamHandler()
# sh.setLevel(logging.INFO)
# sh.setFormatter(fileFormatter)
# logger.addHandler(sh)
