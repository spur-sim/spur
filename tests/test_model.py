# test_spur.py
from spur import __version__
from spur.core import Model
from spur.core.route import Route
from spur.core.exception import NotUniqueIDError

import pytest


def test_version():
    assert __version__ == "0.0.1"


def test_model_init():
    model = Model()
    print(model)


def test_not_unique_train_id(toy_model_with_components):
    r = Route()
    r.append(toy_model_with_components.components[0])
    r.append(toy_model_with_components.components[1])
    with pytest.raises(NotUniqueIDError):
        toy_model_with_components.add_train(1, 20, r)
        toy_model_with_components.add_train(1, 20, r)
