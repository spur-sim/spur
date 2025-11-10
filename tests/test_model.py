#!/usr/bin/env python3

import pathlib

from spur import __version__
from spur.core import Model
from spur.core.route import Route
from spur.core.exception import NotUniqueIDError

from spur.io.formats import read_components_json, read_tours_json, read_routes_json

import pytest

# Tests needed
# - Build and run model with input data (Line 4?)
# - Stop and start model


class TestModelInitialization:
    def test_version(self):
        assert __version__ == "0.0.1"

    def test_initialization(self):
        model = Model()
        print(model)

    def test_not_unique_train_id(self, toy_model_with_components):
        r = Route()
        r.append(toy_model_with_components.components[0])
        r.append(toy_model_with_components.components[1])
        with pytest.raises(NotUniqueIDError):
            toy_model_with_components.add_train(1, 20, r)
            toy_model_with_components.add_train(1, 20, r)
