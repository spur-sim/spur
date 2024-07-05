import pytest

from spur.core import Model
from spur.core.component import TimedTrack


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
