# test_spur.py
from spur import __version__
from spur.core import Model


def test_version():
    assert __version__ == "0.0.1"


def test_model_init():
    model = Model()
    print(model)


def test_model_add_train():
    model = Model()
    model.add_train("ABC", "1", "2", "A", 50)
