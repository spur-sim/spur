#!/usr/bin/env python3

import pathlib

from spur import __version__
from spur.core import Model
from spur.core.route import Route
from spur.core.exception import NotUniqueIDError

import pytest

# Tests needed
# - Build and run model with input data (Line 4?)
# - Stop and start model


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


class TestModelLoad:
    def test_add_components_from_json_file(self, components_json_file):
        m = Model()
        m.add_components_from_json_file(components_json_file)
        assert len(m.components) == 16

    def test_add_routes_and_tours_from_json_file(
        self, components_json_file, routes_json_file, tours_json_file
    ):
        m = Model()
        m.add_components_from_json_file(components_json_file)
        m.add_routes_and_tours_from_json_files(routes_json_file, tours_json_file)
