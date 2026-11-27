"""Tests of the two-track components run through a model: double track kept
to one direction a track, and the station whose dwell grows with headway."""

import numpy as np
import pytest

from spur.core import Model
from spur.core.component import HeadwayDwellStation, MultiBlockTrack, MultiTrackStation, TimedTrack
from spur.core.jitter import GaussianJitter
from spur.core.route import Route
from spur.core.tour import Tour

AMPLE = 20  # capacity of the tracks either side, so only the middle component can hold a train up


def _line(model, component_type, **args):
    """west -- middle -- east, where `middle` is the component under test."""
    west = model._add_component(TimedTrack, "a", "b", "W", traversal_time=10, capacity=AMPLE)
    middle = model._add_component(component_type, "b", "c", "M", **args)
    east = model._add_component(TimedTrack, "c", "d", "E", traversal_time=10, capacity=AMPLE)
    return west, middle, east


def _send(model, uid, components, at=0):
    route = Route()
    for i, component in enumerate(components):
        # A train sets off when it is due to arrive at its first component
        route.append(component, arrival=at if i == 0 else None)
    tour = Tour(creation_time=at, deletion_time=100_000)
    tour.append(route)
    model.add_train(uid, max_speed=50, tour=tour)


def _visits(model, component):
    """{train: (time in, time out)} at a component."""
    times = {}
    for event in model.events:
        if event.component_uid == component.uid:
            times.setdefault(event.train_uid, {})[event.event.value] = event.time
    return {train: (t["IN"], t["OUT"]) for train, t in times.items()}


def _run(model, until=10_000):
    model.start()
    model.run(until=until)


class TestDirectionalMultiBlockTrack:
    def test_a_second_train_the_same_way_waits_for_the_first(self):
        m = Model()
        west, track, east = _line(
            m, MultiBlockTrack, num_tracks=2, num_blocks=1, traversal_time=100, directional=True
        )
        _send(m, "T-1", (west, track, east))
        _send(m, "T-2", (west, track, east))
        _run(m)
        (_, first_out), (second_in, _) = sorted(_visits(m, track).values())
        assert second_in >= first_out

    def test_without_it_the_second_train_takes_the_other_track(self):
        m = Model()
        west, track, east = _line(m, MultiBlockTrack, num_tracks=2, num_blocks=1, traversal_time=100)
        _send(m, "T-1", (west, track, east))
        _send(m, "T-2", (west, track, east))
        _run(m)
        (first_in, _), (second_in, _) = sorted(_visits(m, track).values())
        assert first_in == second_in

    def test_trains_in_opposite_directions_pass_each_other(self):
        m = Model()
        west, track, east = _line(
            m, MultiBlockTrack, num_tracks=2, num_blocks=1, traversal_time=100, directional=True
        )
        _send(m, "EAST", (west, track, east))
        _send(m, "WEST", (east, track, west))
        _run(m)
        visits = _visits(m, track)
        assert visits["EAST"] == visits["WEST"] == (10, 110)

    def test_each_direction_may_take_its_own_time(self):
        m = Model()
        west, track, east = _line(
            m, MultiBlockTrack, num_tracks=2, num_blocks=2, traversal_time=100,
            traversal_time_vu=140, directional=True,
        )
        _send(m, "EAST", (west, track, east))
        _send(m, "WEST", (east, track, west))
        _run(m)
        visits = _visits(m, track)
        assert visits["EAST"] == (10, 110)
        assert visits["WEST"] == (10, 150)

    def test_a_train_follows_one_block_behind(self):
        m = Model()
        west, track, east = _line(
            m, MultiBlockTrack, num_tracks=2, num_blocks=4, traversal_time=100, directional=True
        )
        _send(m, "T-1", (west, track, east))
        _send(m, "T-2", (west, track, east))
        _run(m)
        (first_in, _), (second_in, _) = sorted(_visits(m, track).values())
        assert second_in - first_in == 25

    def test_block_times_add_up_to_the_traversal_time(self, toy_model_base):
        track = MultiBlockTrack(toy_model_base, "C-1", 1, 3, 100)
        assert track._draw_block_times() == [34, 33, 33]

    def test_jitter_is_drawn_once_for_the_whole_traversal(self):
        m = Model(seed=1)
        jitter = GaussianJitter(mean=0, std=20)
        _, track, _ = _line(
            m, MultiBlockTrack, num_tracks=1, num_blocks=4, traversal_time=400, jitter=jitter
        )
        totals = [sum(track._draw_block_times()) for _ in range(4000)]
        # Drawn block by block, the spread would be 20 / sqrt(4) = 10
        assert np.std(totals) == pytest.approx(20, abs=1.5)
        assert np.mean(totals) == pytest.approx(400, abs=1.5)


    def test_jitter_may_be_scaled_for_one_direction(self):
        m = Model(seed=1)
        jitter = GaussianJitter(mean=0, std=20)
        _, track, _ = _line(
            m, MultiBlockTrack, num_tracks=2, num_blocks=2, traversal_time=400,
            jitter_scale_vu=0.25, jitter=jitter,
        )
        forward = [sum(track._draw_block_times(1)) for _ in range(4000)]
        backward = [sum(track._draw_block_times(-1)) for _ in range(4000)]
        assert np.std(forward) == pytest.approx(20, abs=1.5)
        assert np.std(backward) == pytest.approx(5, abs=0.6)


class TestHeadwayDwellStation:
    VALUES = dict(
        intercept_uv=20, boarding_rate_uv=0.1, boarding_time_uv=0.5,
        alighting_rate_uv=0.05, alighting_time_uv=0.4, first_dwell_uv=30,
    )

    def test_dwell_grows_with_the_time_since_the_last_train(self):
        m = Model()
        west, station, east = _line(m, HeadwayDwellStation, **self.VALUES)
        _send(m, "T-1", (west, station, east), at=0)
        _send(m, "T-2", (west, station, east), at=200)
        _send(m, "T-3", (west, station, east), at=600)
        _run(m)
        dwell = {train: out - into for train, (into, out) in _visits(m, station).items()}
        assert dwell["T-1"] == 30  # the first train's own dwell
        assert dwell["T-2"] == 20 + 0.5 * 0.1 * 200 + 0.4 * 0.05 * 200
        assert dwell["T-3"] == 20 + 0.5 * 0.1 * 400 + 0.4 * 0.05 * 400

    def test_each_direction_keeps_its_own_values_and_headway(self):
        m = Model()
        west, station, east = _line(
            m, HeadwayDwellStation, **self.VALUES, intercept_vu=50, boarding_rate_vu=0
        )
        _send(m, "EAST-1", (west, station, east), at=0)
        _send(m, "WEST-1", (east, station, west), at=100)
        _send(m, "WEST-2", (east, station, west), at=400)
        _run(m)
        dwell = {train: out - into for train, (into, out) in _visits(m, station).items()}
        assert dwell["WEST-1"] == 50  # first that way, though a train has called the other way
        assert dwell["WEST-2"] == 50 + 0.4 * 0.05 * 300

    def test_a_direction_left_out_copies_the_other(self):
        m = Model()
        west, station, east = _line(m, HeadwayDwellStation, **self.VALUES)
        _send(m, "WEST-1", (east, station, west), at=0)
        _send(m, "WEST-2", (east, station, west), at=200)
        _run(m)
        dwell = {train: out - into for train, (into, out) in _visits(m, station).items()}
        assert dwell["WEST-1"] == 20  # first_dwell_vu defaults to that direction's intercept
        assert dwell["WEST-2"] == 20 + 0.5 * 0.1 * 200 + 0.4 * 0.05 * 200

    def test_one_train_at_a_time_in_each_direction(self):
        m = Model()
        west, station, east = _line(m, HeadwayDwellStation, intercept_uv=100)
        _send(m, "EAST-1", (west, station, east))
        _send(m, "EAST-2", (west, station, east))
        _send(m, "WEST-1", (east, station, west))
        _run(m)
        visits = _visits(m, station)
        assert visits["EAST-2"][0] >= visits["EAST-1"][1]
        assert visits["WEST-1"][0] == visits["EAST-1"][0]

    def test_a_waiting_train_does_not_hold_up_one_going_the_other_way(self):
        m = Model()
        west, station, east = _line(m, HeadwayDwellStation, intercept_uv=100)
        _send(m, "EAST-1", (west, station, east), at=0)
        _send(m, "EAST-2", (west, station, east), at=20)   # queues behind EAST-1
        _send(m, "WEST-1", (east, station, west), at=40)   # arrives while EAST-2 is queued
        _run(m)
        visits = _visits(m, station)
        assert visits["WEST-1"][0] == 50
        assert visits["EAST-2"][0] == visits["EAST-1"][1]

    def test_the_next_train_waits_for_the_track_to_clear(self):
        m = Model()
        west, station, east = _line(m, HeadwayDwellStation, intercept_uv=100, clearance_time=30)
        _send(m, "EAST-1", (west, station, east))
        _send(m, "EAST-2", (west, station, east))
        _send(m, "WEST-1", (east, station, west), at=115)
        _run(m)
        visits = _visits(m, station)
        assert visits["EAST-2"][0] == visits["EAST-1"][1] + 30
        assert visits["WEST-1"][0] == 125  # the other direction's track is its own

    def test_a_direction_that_does_not_stop_runs_through(self):
        m = Model()
        west, station, east = _line(
            m, HeadwayDwellStation, intercept_uv=30, stops_vu=False, pass_time=5
        )
        _send(m, "EAST", (west, station, east))
        _send(m, "WEST", (east, station, west))
        _run(m)
        dwell = {train: out - into for train, (into, out) in _visits(m, station).items()}
        assert dwell == {"EAST": 30, "WEST": 5}

    def test_max_dwell_caps_the_dwell(self):
        m = Model()
        west, station, east = _line(m, HeadwayDwellStation, **self.VALUES, max_dwell=40)
        _send(m, "T-1", (west, station, east), at=0)
        _send(m, "T-2", (west, station, east), at=2000)
        _run(m)
        into, out = _visits(m, station)["T-2"]
        assert out - into == 40

    @pytest.mark.parametrize(
        "bad", [dict(intercept_uv=-1), dict(intercept_uv=1, boarding_rate_vu=-1),
                dict(intercept_uv=1, pass_time=-1), dict(intercept_uv=1, max_dwell=-1)]
    )
    def test_negative_values_are_refused(self, toy_model_base, bad):
        with pytest.raises(ValueError):
            HeadwayDwellStation(toy_model_base, "C-1", **bad)


def test_a_train_may_start_its_tour_on_double_track():
    m = Model()
    track = m._add_component(MultiBlockTrack, "a", "b", "T", num_tracks=2, num_blocks=2,
                             traversal_time=40, directional=True)
    west = m._add_component(TimedTrack, "a", "z", "W", traversal_time=10, capacity=AMPLE)
    _send(m, "WEST", (track, west))   # starts on the double track, leaving by node a: v to u
    _run(m)
    assert _visits(m, track)["WEST"] == (0, 40)
    assert track._track_assignments == {}


# A dwell of about 60 steps (Burr with d=2, loc 60, scale 1).
DWELL = dict(dwell_c=2, dwell_d=2, dwell_loc=60, dwell_scale=1)


def _send_stopping(model, uid, components, stop_at, at=0):
    """As `_send`, stopping at the component `stop_at`."""
    route = Route()
    for i, component in enumerate(components):
        route.append(component, arrival=at if i == 0 else None,
                     departure=at if component is stop_at else None)
    tour = Tour(creation_time=at, deletion_time=100_000)
    tour.append(route)
    model.add_train(uid, max_speed=50, tour=tour)


class TestDirectionalMultiTrackStation:
    def _station(self, m, **args):
        return _line(m, MultiTrackStation, num_stopping_tracks=2, num_bypass_tracks=0,
                     bypass_time=20, **DWELL, **args)

    def test_a_second_train_the_same_way_waits_for_the_first(self):
        m = Model()
        west, station, east = self._station(m, directional=True)
        _send_stopping(m, "T-1", (west, station, east), station)
        _send_stopping(m, "T-2", (west, station, east), station)
        _run(m)
        (_, first_out), (second_in, _) = sorted(_visits(m, station).values())
        assert second_in >= first_out

    def test_without_it_the_second_train_takes_the_other_track(self):
        m = Model()
        west, station, east = self._station(m)
        _send_stopping(m, "T-1", (west, station, east), station)
        _send_stopping(m, "T-2", (west, station, east), station)
        _run(m)
        (first_in, _), (second_in, _) = sorted(_visits(m, station).values())
        assert first_in == second_in

    def test_trains_in_opposite_directions_stop_together(self):
        m = Model()
        west, station, east = self._station(m, directional=True)
        _send_stopping(m, "EAST", (west, station, east), station)
        _send_stopping(m, "WEST", (east, station, west), station)
        _run(m)
        visits = _visits(m, station)
        assert visits["EAST"][0] == visits["WEST"][0] == 10

    def test_a_train_passing_through_keeps_to_its_direction(self):
        m = Model()
        west, station, east = self._station(m, directional=True)
        _send_stopping(m, "STOPS", (west, station, east), station)
        _send(m, "PASSES", (west, station, east))
        _run(m)
        visits = _visits(m, station)
        assert visits["PASSES"][0] >= visits["STOPS"][1]

    def test_bypass_tracks_alternate_too(self):
        m = Model()
        west, station, east = _line(m, MultiTrackStation, num_stopping_tracks=2,
                                    num_bypass_tracks=2, bypass_time=20, **DWELL, directional=True)
        _send(m, "EAST-1", (west, station, east))
        _send(m, "EAST-2", (west, station, east))
        _send(m, "WEST", (east, station, west))
        _run(m)
        visits = _visits(m, station)
        # One bypass track and one stopping track each way: both eastbound trains get in
        # at once, and so does the westbound one.
        assert visits["EAST-1"][0] == visits["EAST-2"][0] == visits["WEST"][0] == 10


def _double_track_line(m, directional):
    """Double track, a two-track station, double track: the shape of a
    commuter line between stations."""
    a = m._add_component(TimedTrack, "y", "a", "YW", traversal_time=5, capacity=AMPLE)
    west = m._add_component(MultiBlockTrack, "a", "b", "W", num_tracks=2, num_blocks=1,
                            traversal_time=100, directional=directional)
    station = m._add_component(MultiTrackStation, "b", "c", "S", num_stopping_tracks=2,
                               num_bypass_tracks=0, bypass_time=20, **DWELL,
                               directional=directional)
    east = m._add_component(MultiBlockTrack, "c", "d", "E", num_tracks=2, num_blocks=1,
                            traversal_time=100, directional=directional)
    d = m._add_component(TimedTrack, "d", "z", "ZE", traversal_time=5, capacity=AMPLE)
    return a, west, station, east, d


@pytest.mark.parametrize("directional, finished", [(False, False), (True, True)])
def test_two_trains_each_way_meet_head_on_only_without_direction(directional, finished):
    """Issue #116: two trains each way fill both tracks and wait on each other
    for good, unless each track keeps to one direction."""
    m = Model()
    a, west, station, east, d = _double_track_line(m, directional)
    # The eastbound pair fills the station's tracks just as the westbound pair,
    # a little behind, fills the double track beyond it.
    for i in range(2):
        _send_stopping(m, f"EAST-{i}", (a, west, station, east, d), station)
        _send_stopping(m, f"WEST-{i}", (d, east, station, west, a), station, at=30)
    _run(m)
    done = {t for t, (_, out) in _visits(m, a).items() if t.startswith("WEST")} | \
           {t for t, (_, out) in _visits(m, d).items() if t.startswith("EAST")}
    assert (len(done) == 4) == finished
