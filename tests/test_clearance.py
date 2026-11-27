"""A place a train leaves stays held for the component's clearance time."""

import pytest

from spur.catalog import catalog
from spur.core import Model
from spur.core.component import MultiBlockTrack, MultiTrackStation, SimpleYard, TimedTrack
from spur.core.route import Route
from spur.core.tour import Tour


def _model():
    events = []
    return Model(event_sink=events.append), events


def _run(m, components_per_train, until=1000):
    """One train per list of components, run through them in order."""
    for i, components in enumerate(components_per_train):
        route = Route()
        for c in components:
            route.append(c)
        tour = Tour(creation_time=0, deletion_time=until)
        tour.append(route)
        m.add_train(f"T-{i}", max_speed=50, tour=tour)
    m.start()
    m.run(until=until)


def _times(events, component):
    """{train: (in, out)} on `component`."""
    seen = {}
    for e in events:
        if e.component_uid == component.uid:
            seen.setdefault(e.train_uid, {})[e.event.value] = e.time
    return {t: (v.get("IN"), v.get("OUT")) for t, v in seen.items()}


def _entries(m, times, u="0", v="1"):
    """An entry track per train, reaching the next component at each of `times`."""
    return [
        m._add_component(TimedTrack, u, v, f"E{i}", traversal_time=t)
        for i, t in enumerate(times)
    ]


class TestSimpleComponents:
    def _two_trains(self, clearance):
        m, events = _model()
        a, b = _entries(m, [10, 20])
        c = m._add_component(TimedTrack, "1", "2", "C", traversal_time=100, clearance_time=clearance)
        out = m._add_component(TimedTrack, "2", "3", "X", traversal_time=5, capacity=2)
        _run(m, [[a, c, out], [b, c, out]])
        return _times(events, c)

    def test_next_train_waits_out_the_clearance(self):
        # T-0 holds C from 10 to 110; the place clears 30 later.
        assert self._two_trains(30)["T-1"][0] == 140

    def test_no_clearance_is_as_before(self):
        assert self._two_trains(0)["T-1"][0] == 110

    def test_a_free_place_is_not_held(self):
        m, events = _model()
        a, b = _entries(m, [10, 20])
        c = m._add_component(
            TimedTrack, "1", "2", "C", traversal_time=100, capacity=2, clearance_time=30
        )
        out = m._add_component(TimedTrack, "2", "3", "X", traversal_time=5, capacity=2)
        _run(m, [[a, c, out], [b, c, out]])
        assert _times(events, c)["T-1"][0] == 20

    def test_negative_clearance_is_refused(self):
        m, _ = _model()
        with pytest.raises(ValueError):
            m._add_component(TimedTrack, "1", "2", "C", traversal_time=100, clearance_time=-1)


class TestMultiBlockTrack:
    def test_following_train_waits_for_each_block_to_clear(self):
        m, events = _model()
        a, b = _entries(m, [10, 20])
        # Two blocks of 50. Block 0 is left at 60 and clear at 85; block 1 is
        # left at 110 and clear at 135, so T-1 runs 75 behind T-0 throughout.
        c = m._add_component(
            MultiBlockTrack, "1", "2", "C", num_tracks=1, num_blocks=2, traversal_time=100,
            clearance_time=25,
        )
        out = m._add_component(TimedTrack, "2", "3", "X", traversal_time=5, capacity=2)
        _run(m, [[a, c, out], [b, c, out]])
        times = _times(events, c)
        assert times["T-0"] == (10, 110)
        assert times["T-1"] == (85, 185)

    def test_opposing_train_waits_for_the_last_block_to_clear(self):
        m, events = _model()
        a = m._add_component(TimedTrack, "0", "1", "A", traversal_time=10)
        c = m._add_component(
            MultiBlockTrack, "1", "2", "C", num_tracks=1, num_blocks=2, traversal_time=100,
            clearance_time=25,
        )
        b = m._add_component(TimedTrack, "2", "3", "B", traversal_time=5)
        b_back = m._add_component(TimedTrack, "3", "2", "Bk", traversal_time=20)
        a_back = m._add_component(TimedTrack, "1", "0", "Ak", traversal_time=5)
        _run(m, [[a, c, b], [b_back, c, a_back]])
        # T-0 leaves the single track at 110; its last block clears at 135.
        assert _times(events, c)["T-1"][0] == 135

    def test_no_clearance_is_as_before(self):
        m, events = _model()
        a, b = _entries(m, [10, 20])
        c = m._add_component(
            MultiBlockTrack, "1", "2", "C", num_tracks=1, num_blocks=2, traversal_time=100
        )
        out = m._add_component(TimedTrack, "2", "3", "X", traversal_time=5, capacity=2)
        _run(m, [[a, c, out], [b, c, out]])
        times = _times(events, c)
        assert times["T-1"] == (60, 160)


class TestMultiTrackStation:
    def test_next_train_waits_for_the_track_to_clear(self):
        m, events = _model()
        a, b = _entries(m, [10, 20])
        # No bypass track, so both trains use the one stopping track, for
        # bypass_time each: T-0 from 10 to 60, then the track clears at 100.
        c = m._add_component(
            MultiTrackStation, "1", "2", "S", num_stopping_tracks=1, num_bypass_tracks=0,
            bypass_time=50, dwell_c=2, dwell_d=2, dwell_loc=60, dwell_scale=1, clearance_time=40,
        )
        out = m._add_component(TimedTrack, "2", "3", "X", traversal_time=5, capacity=2)
        _run(m, [[a, c, out], [b, c, out]])
        assert _times(events, c)["T-1"][0] == 100


def test_catalogue_offers_clearance_on_every_component_but_the_yard():
    for t in catalog().components:
        names = {p.name for p in t.parameters}
        assert ("clearance_time" in names) == (t.name != SimpleYard.__name__), t.name
