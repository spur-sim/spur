import math
import pytest

from spur.core.component import (
    MultiBlockTrack,
    MultiTrackStation,
    SimpleCrossover,
    TimedStation,
    TimedTrack,
    PhysicsTrack,
)
from spur.core.jitter import NoJitter
from spur.core.train import Train


class TestMultiBlockTrack:
    def test_initialization_with_defaults(self, toy_model_base):
        c = MultiBlockTrack(toy_model_base, "C-1", 2, 2, 50)
        assert c.uid == "C-1"
        assert c._num_tracks == 2
        assert c._num_blocks == 2
        assert type(c.jitter) == NoJitter
        assert c._block_traversal_time == 25
        assert c.collection == None

    @pytest.mark.parametrize(
        ("tracks", "blocks"),
        [(-2, 2), (2, -2), (-2, -2)],
    )
    def test_initialization_with_invalid_tracks_blocks(
        self, toy_model_base, tracks, blocks
    ):
        with pytest.raises(ValueError):
            c = MultiBlockTrack(toy_model_base, "C-1", tracks, blocks, 50)


class TestPhysicsTrack:
    def test_initialization_with_defaults(self, toy_model_base):
        c = PhysicsTrack(toy_model_base, "C-1", 10, 100)
        assert c.uid == "C-1"
        assert c.track_speed == 100
        assert type(c.jitter) == NoJitter
        assert c.collection == None

    def test_initialization_with_invalid_track_speed(self, toy_model_base):
        with pytest.raises(ValueError):
            c = PhysicsTrack(toy_model_base, "C-1", 10, -100)

    def test_initialization_with_invalid_length(self, toy_model_base):
        with pytest.raises(ValueError):
            c = PhysicsTrack(toy_model_base, "C-1", 0, 100)


class TestSimpleCrossover:
    def test_initialization_with_defaults(self, toy_model_base):
        c = SimpleCrossover(toy_model_base, "C-1", 10)
        assert c.uid == "C-1"
        assert c.traversal_time == 10
        assert type(c.jitter) == NoJitter
        assert c.collection == None

    def test_initialization_with_invalid_inputs(self, toy_model_base):
        with pytest.raises(ValueError):
            c = SimpleCrossover(toy_model_base, "C-1", -10)


class TestTimedStation:
    def test_initialization_with_defaults(self, toy_model_base):
        c = TimedStation(toy_model_base, "S-1", 10, 10, 50)
        assert c.uid == "S-1"
        assert c._mean_boarding == 10
        assert c._mean_alighting == 10
        assert c._traversal_time == 50
        assert type(c.jitter) == NoJitter
        assert c.collection == None

    @pytest.mark.parametrize(
        ("mean_boarding", "mean_alighting", "traversal_time"),
        [(-10, 10, 50), (-10, -10, 50), (10, 10, -50)],
    )
    def test_initialization_with_invalid_inputs(
        self, toy_model_base, mean_boarding, mean_alighting, traversal_time
    ):
        with pytest.raises(ValueError):
            c = TimedStation(
                toy_model_base, "S-1", mean_boarding, mean_alighting, traversal_time
            )


class TestTimedTrack:
    def test_initialization_with_defaults(self, toy_model_base):
        c = TimedTrack(toy_model_base, "C-1", 10)
        assert c.uid == "C-1"
        assert c.traversal_time == 10
        assert type(c.jitter) == NoJitter
        assert c.collection == None

    def test_initialization_with_invalid_capacity(self, toy_model_base):
        with pytest.raises(ValueError):
            c = TimedTrack(toy_model_base, "C-1", 10, capacity=-1)

    def test_initialization_with_invalid_traversal_time(self, toy_model_base):
        with pytest.raises(ValueError):
            c = TimedTrack(toy_model_base, "C-1", -10)
