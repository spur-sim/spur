import math
import pytest

from spur.core.component import (
    DynamicDwellStation,
    MultiBlockTrack,
    MultiTrackStation,
    SimpleCrossover,
    TimedStation,
    TimedTrack,
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
        c = TimedStation(toy_model_base, "S-1", 50)
        assert c.uid == "S-1"
        assert c.traversal_time == 50
        assert type(c.jitter) == NoJitter
        assert c.collection == None

    def test_initialization_with_invalid_traversal_time(self, toy_model_base):
        with pytest.raises(ValueError):
            c = TimedStation(toy_model_base, "S-1", -50)

    def test_do_dwells_for_traversal_time(self, toy_model_base):
        c = TimedStation(toy_model_base, "S-1", 50)
        toy_model_base.process(c.do(None))
        toy_model_base.run()
        assert toy_model_base.now == 50


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


class TestDynamicDwellStation:
    def test_initialization_with_defaults(self, toy_model_base):
        c = DynamicDwellStation(toy_model_base, "S-1", 0.1, 5, 2)
        assert c.uid == "S-1"
        assert c._mean_arrival_rate == 0.1
        assert c._coefficient_a == 5
        assert c._coefficient_b == 2
        assert type(c.jitter) == NoJitter
        assert c.collection == None

    @pytest.mark.parametrize(
        ("mean_arrival_rate", "coefficient_a", "coefficient_b"),
        [(-0.1, 5, 2), (0.1, -5, 2), (0.1, 5, -2)],
    )
    def test_initialization_with_invalid_inputs(
        self, toy_model_base, mean_arrival_rate, coefficient_a, coefficient_b
    ):
        with pytest.raises(ValueError):
            c = DynamicDwellStation(
                toy_model_base, "S-1", mean_arrival_rate, coefficient_a, coefficient_b
            )

    def test_first_dwell_has_no_headway(self, toy_model_base):
        # No previous departure recorded yet, so estimated passengers (and
        # therefore the headway-dependent part of dwell) is zero.
        c = DynamicDwellStation(toy_model_base, "S-1", 1.0, 10, 2)
        toy_model_base.process(c.do(None))
        toy_model_base.run()
        assert toy_model_base.now == 10

    def test_second_dwell_scales_with_headway_since_first_departure(
        self, toy_model_base
    ):
        c = DynamicDwellStation(toy_model_base, "S-1", 1.0, 10, 2)
        toy_model_base.process(c.do(None))
        toy_model_base.run()
        assert toy_model_base.now == 10  # First train departs at t=10.

        # Let 10 more ticks pass with nothing else happening, so the second
        # train's headway since the first departure is well-defined.
        toy_model_base.run(until=20)
        assert toy_model_base.now == 20

        toy_model_base.process(c.do(None))
        toy_model_base.run()
        # Headway since first departure is 20 - 10 = 10, so estimated
        # passengers = 1.0 * 10 = 10, and dwell = 10 + 2 * 10 = 30,
        # departing at t=50.
        assert toy_model_base.now == 50
