import pytest

from spur.core import Model
from spur.core.component import PhysicsTrack


@pytest.fixture
def toy_model_base():
    """Set up a basic empty toy model."""
    return Model()


@pytest.fixture
def toy_model_with_components(toy_model_base):
    """Return a basic toy model with some components attached for testing."""
    toy_model_base.add_component(PhysicsTrack, "1", "2", "A", length=80, track_speed=25)
    toy_model_base.add_component(PhysicsTrack, "2", "3", "A", length=80, track_speed=25)
    toy_model_base.add_component(PhysicsTrack, "3", "4", "A", length=80, track_speed=25)
    return toy_model_base
