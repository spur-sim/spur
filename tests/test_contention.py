"""Integration tests exercising real resource/BlockExclusiveZone contention.

Unlike tests/test_collection.py (which calls BlockExclusiveZone methods
directly and manually, never through a running simulation) these tests
drive multiple trains through a running Model and assert on the resulting
queuing/timing behaviour.
"""

from spur.core import Model
from spur.core.collection import BlockExclusiveZone
from spur.core.component import TimedTrack
from spur.core.route import Route
from spur.core.tour import Tour
from spur.core.train import Train


def _read_agent_log(path):
    """Parse a Model's agent_log_file into a list of IN/OUT event dicts."""
    events = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        now_str, logger_name, event_type, component_uid, _component_name = line.split(",")
        events.append(
            {
                "time": int(now_str),
                "train": logger_name.rsplit(".", 1)[-1],
                "event": event_type,
                "component": component_uid,
            }
        )
    return events


def _intervals_for_component(events, component_uid):
    """Return {train_id: (in_time, out_time)} for a given component."""
    intervals = {}
    for e in events:
        if e["component"] != component_uid:
            continue
        intervals.setdefault(e["train"], {})[e["event"]] = e["time"]
    return {train: (v["IN"], v["OUT"]) for train, v in intervals.items()}


def _single_component_tour(component):
    route = Route()
    route.append(component)
    tour = Tour(creation_time=0, deletion_time=1000)
    tour.append(route)
    return tour


class TestCapacityLimitedResource:
    def test_second_train_waits_for_first_to_release(self, tmp_path):
        agent_log = tmp_path / "agent.log"
        m = Model(agent_log_file=str(agent_log))
        c = m._add_component(
            TimedTrack, "1", "2", "A", traversal_time=100, capacity=1
        )

        m.add_train("T-1", max_speed=50, tour=_single_component_tour(c))
        m.add_train("T-2", max_speed=50, tour=_single_component_tour(c))

        m.start()
        m.run(until=250)

        intervals = _intervals_for_component(_read_agent_log(agent_log), c.uid)
        assert set(intervals.keys()) == {"T-1", "T-2"}
        (a_in, a_out), (b_in, b_out) = intervals.values()

        # The two trains' occupancy of the capacity-1 resource must never
        # overlap in simulated time.
        assert a_out <= b_in or b_out <= a_in


class TestBlockExclusiveZone:
    def _build_model(self, agent_log_path, num_trains):
        # Zone component capacity must be >= num_trains: SpurResource's
        # own plain-capacity check short-circuits before ever calling
        # can_accept_agent, so a capacity of 1 would make the raw resource
        # (not the BlockExclusiveZone) the thing doing the gating. Giving
        # the zone components generous capacity ensures BlockExclusiveZone
        # itself is what's actually under test.
        m = Model(agent_log_file=str(agent_log_path))
        bez = BlockExclusiveZone(m, "Z-1")

        zone_1 = m._add_component(
            TimedTrack, "1", "2", "A", traversal_time=15, capacity=num_trains, collection=bez
        )
        zone_2 = m._add_component(
            TimedTrack, "2", "3", "A", traversal_time=15, capacity=num_trains, collection=bez
        )
        exit_ = m._add_component(TimedTrack, "3", "4", "A", traversal_time=5, capacity=num_trains)

        for i in range(num_trains):
            # Each train gets its own entry component with a staggered
            # traversal time, so trains reach the zone at distinct
            # simulated ticks rather than simultaneously.
            entry = m._add_component(
                TimedTrack, "0", f"1-{i}", f"E{i}", traversal_time=10 * (i + 1), capacity=1
            )
            route = Route()
            for component in (entry, zone_1, zone_2, exit_):
                route.append(component)
            tour = Tour(creation_time=0, deletion_time=1000)
            tour.append(route)
            m.add_train(f"T-{i}", max_speed=50, tour=tour)

        return m, bez, zone_1

    def test_second_train_queues_then_enters_after_release(self, tmp_path):
        agent_log = tmp_path / "agent.log"
        m, bez, zone_1 = self._build_model(agent_log, num_trains=2)
        m.start()

        # T-0 reaches the zone at t=10 and occupies it until t=40 (15+15).
        # T-1 reaches the zone at t=20, while T-0 still occupies it, and
        # must queue. Checkpoints are offset by +1 since simpy's
        # run(until=X) stops before processing events scheduled exactly
        # at X.
        m.run(until=21)
        assert bez.occupied is True
        assert len(bez.wait_queue) == 1

        # At t=40 T-0 releases the zone (requesting the exit component);
        # T-1 should now have been granted entry.
        m.run(until=41)
        assert bez.occupied is True
        assert len(bez.wait_queue) == 0

        m.run(until=100)

        intervals = _intervals_for_component(_read_agent_log(agent_log), zone_1.uid)
        assert set(intervals.keys()) == {"T-0", "T-1"}
        (a_in, a_out), (b_in, b_out) = intervals.values()
        assert a_out <= b_in or b_out <= a_in

    def test_fifo_ordering_with_multiple_waiters(self, tmp_path):
        agent_log = tmp_path / "agent.log"
        m, bez, zone_1 = self._build_model(agent_log, num_trains=3)
        m.start()

        # T-0 occupies the zone from t=10 to t=40; T-1 arrives at t=20 and
        # queues behind it.
        m.run(until=21)
        assert bez.occupied is True
        assert len(bez.wait_queue) == 1

        # T-2 arrives at t=30 and queues behind T-1. The zone's own wait
        # queue is first come, first served, so entry order follows arrival.
        m.run(until=150)

        events = _read_agent_log(agent_log)
        in_times = {
            e["train"]: e["time"]
            for e in events
            if e["component"] == zone_1.uid and e["event"] == "IN"
        }
        # All three trains must be granted entry in the order they
        # originally arrived at the zone: T-0, then T-1, then T-2.
        assert in_times["T-0"] < in_times["T-1"] < in_times["T-2"]


class TestBlockExclusiveZoneFirstSegmentRegression:
    def test_release_does_not_crash_when_waiter_has_no_current_segment(self, tmp_path):
        """A train whose very first-ever tour segment is inside a contended
        BlockExclusiveZone has `current_segment is None` while it waits.
        BlockExclusiveZone.release_agent() must not crash when it releases
        the zone to such a waiter (regression for a bug found while writing
        the contention tests above).
        """
        agent_log = tmp_path / "agent.log"
        m = Model(agent_log_file=str(agent_log))
        bez = BlockExclusiveZone(m, "Z-1")

        zone = m._add_component(
            TimedTrack, "1", "2", "A", traversal_time=50, capacity=1, collection=bez
        )
        exit_ = m._add_component(TimedTrack, "2", "3", "A", traversal_time=10, capacity=2)

        for uid in ("T-0", "T-1"):
            route = Route()
            route.append(zone)
            route.append(exit_)
            tour = Tour(creation_time=0, deletion_time=1000)
            tour.append(route)
            m.add_train(uid, max_speed=50, tour=tour)

        m.start()
        # Both trains request the zone at t=0 as their first-ever segment;
        # the losing train is queued with current_segment still None. This
        # must not raise when the winner releases the zone.
        m.run(until=110)

        intervals = _intervals_for_component(_read_agent_log(agent_log), zone.uid)
        assert set(intervals.keys()) == {"T-0", "T-1"}


class TestBlockExclusiveZoneHeadOfLineRegression:
    def test_train_inside_zone_is_not_blocked_by_refused_train_ahead_in_queue(self, tmp_path):
        """A train refused by a zone must not block a request queued behind it
        on the same component that the zone would allow.

        T-in enters the zone and is on its way to the zone's last component,
        `station`. T-out reaches `station` from outside first, so its request
        heads the station's queue, and the zone refuses it because T-in holds
        the zone. When T-in then asks for `station`, its request must still be
        tried: it is moving within the zone, and the station is free.
        Otherwise each train waits on the other for good (found as a head-on
        gridlock on a single-track line).
        """
        agent_log = tmp_path / "agent.log"
        m = Model(agent_log_file=str(agent_log))
        bez = BlockExclusiveZone(m, "Z-1")

        inside = m._add_component(
            TimedTrack, "1", "2", "A", traversal_time=50, capacity=1, collection=bez
        )
        station = m._add_component(
            TimedTrack, "2", "3", "A", traversal_time=20, capacity=1, collection=bez
        )
        entry_in = m._add_component(TimedTrack, "0", "1", "A", traversal_time=1, capacity=1)
        exit_in = m._add_component(TimedTrack, "3", "4", "A", traversal_time=5, capacity=1)
        entry_out = m._add_component(TimedTrack, "5", "3", "A", traversal_time=10, capacity=1)
        exit_out = m._add_component(TimedTrack, "2", "6", "A", traversal_time=5, capacity=1)

        for uid, components in (
            ("T-in", (entry_in, inside, station, exit_in)),
            ("T-out", (entry_out, station, exit_out)),
        ):
            route = Route()
            for component in components:
                route.append(component)
            tour = Tour(creation_time=0, deletion_time=1000)
            tour.append(route)
            m.add_train(uid, max_speed=50, tour=tour)

        m.start()
        m.run(until=200)

        intervals = _intervals_for_component(_read_agent_log(agent_log), station.uid)
        assert set(intervals.keys()) == {"T-in", "T-out"}
        assert intervals["T-in"][1] <= intervals["T-out"][0]
