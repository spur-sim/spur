import pathlib
import pytest

from spur.core import Model
from spur.core.component import TimedTrack
from spur.core.route import Route
from spur.core.tour import Tour

# Test data
DATA_DIRECTORY = pathlib.Path(__file__).resolve().parent / "data"
COMPONENTS = DATA_DIRECTORY / "test_components.json"
ROUTES = DATA_DIRECTORY / "test_routes.json"
TOURS = DATA_DIRECTORY / "test_tours.json"
TRAINS = DATA_DIRECTORY / "test_trains.json"


@pytest.fixture
def components_json_file():
    """Return the json file of components"""
    return COMPONENTS


@pytest.fixture
def routes_json_file():
    """Return the json file of routes"""
    return ROUTES


@pytest.fixture
def tours_json_file():
    """Return the json file of tours"""
    return TOURS


@pytest.fixture
def trains_json_file():
    """Return the json file of trains"""
    return TRAINS


@pytest.fixture
def toy_model_base():
    """Set up a basic empty toy model."""
    return Model()


@pytest.fixture
def toy_model_with_components(toy_model_base):
    """Return a basic toy model with some components attached for testing."""
    toy_model_base.add_component(
        TimedTrack, "1", "2", "A", traversal_time=180, capacity=1
    )
    toy_model_base.add_component(
        TimedTrack, "2", "3", "A", traversal_time=80, capacity=2
    )
    toy_model_base.add_component(
        TimedTrack, "3", "4", "A", traversal_time=80, capacity=1
    )
    return toy_model_base


@pytest.fixture
def toy_model_tour(toy_model_with_components):
    r = Route()
    for c in toy_model_with_components.components:
        r.append(c)
    t = Tour(creation_time=10, deletion_time=100)
    t.append(r)
    return t
