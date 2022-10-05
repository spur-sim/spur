# test_spur.py
from spur import __version__
from spur.core import Model


def test_version():
    assert __version__ == "0.0.1"


def test_model_init():
    model = Model()
    print(model)
