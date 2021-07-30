import pytest

from spur.core import Model
from spur.core.train import Train
from spur.core.base import StatusException


def test_set_valid_train_status():
    model = Model()
    t = model.add_train("ABC", "1", "2", "A", 50)
    t.status = Train.STATUS_STOPPED


def test_set_invalid_train_status():
    model = Model()
    with pytest.raises(StatusException):
        t = model.add_train("ABC", "1", "2", "A", 50)
        t.status = 42
