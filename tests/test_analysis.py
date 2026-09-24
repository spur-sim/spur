import pytest

from spur.analysis import _scheduled_segments, analyze
from spur.core import Model
from spur.core.event import SimEvent
from spur.core.exception import InputMismatchError
from spur.io.formats import (
    read_components_json,
    read_routes_json,
    read_tours_json,
    read_trains_json,
)

Y1 = "a-b-Y"
T1 = "b-c-A"
S1 = "c-d-S"
T2 = "d-e-A"
Y2 = "e-f-Y"
T3 = "f-g-A"

TYPES = {Y1: "SimpleYard", T1: "TimedTrack", S1: "SimpleStation", T2: "TimedTrack",
         Y2: "SimpleYard", T3: "TimedTrack"}


def _ref(uid):
    u, v, key = uid.split("-")
    return {"u": u, "v": v, "key": key}


# Route R1 ends at Y2 and route R2 starts there, so Y2 is one visit that takes
# its departure (500) from R2's first entry. Y1 is visited twice.
PROJECT = {
    "components": [],
    "routes": [
        {"name": "R1", "components": [_ref(c) for c in (Y1, T1, S1, T2, Y2)]},
        {"name": "R2", "components": [_ref(c) for c in (Y2, T3, Y1)]},
    ],
    "tours": [
        {
            "name": "Tour-A",
            "creation_time": 0,
            "deletion_time": 1000,
            "routes": [
                {
                    "name": "R1",
                    "args": [
                        {"departure": 100},
                        None,
                        {"arrival": 200, "departure": 260},
                        None,
                        {"departure": 9999},  # replaced by R2's first entry
                    ],
                },
                {"name": "R2", "args": [{"departure": 500}, None, {"departure": 700}]},
            ],
        }
    ],
    "trains": [
        {"name": "T-0", "max_speed": 50, "tour": "Tour-A"},
        {"name": "T-1", "max_speed": 50, "tour": "Tour-A"},
    ],
}


def ev(time, kind, train, comp):
    return SimEvent(
        time=time, event=kind, train_uid=train, component_uid=comp,
        component_type=TYPES[comp],
    )


# T-0 makes the whole tour and is still in Y1 (second visit) when the run ends.
# T-1 follows one step behind and is still in S1. Each IN is emitted before the
# OUT of the component being left, as the engine does.
EVENTS = [
    ev(0, "IN", "T-0", Y1),
    ev(0, "IN", "T-1", Y1),
    ev(100, "IN", "T-0", T1), ev(100, "OUT", "T-0", Y1),
    ev(100, "IN", "T-1", T1), ev(100, "OUT", "T-1", Y1),
    ev(230, "IN", "T-0", S1), ev(230, "OUT", "T-0", T1),
    ev(260, "IN", "T-1", S1), ev(260, "OUT", "T-1", T1),
    ev(290, "IN", "T-0", T2), ev(290, "OUT", "T-0", S1),
    ev(400, "IN", "T-0", Y2), ev(400, "OUT", "T-0", T2),
    ev(510, "IN", "T-0", T3), ev(510, "OUT", "T-0", Y2),
    ev(650, "IN", "T-0", Y1), ev(650, "OUT", "T-0", T3),
    ev(800, "LOC", "T-0", Y1),
    ev(800, "LOC", "T-1", S1),
]


def _visits(analysis, train):
    return [v for v in analysis.visits if v.train_uid == train]


class TestVisits:
    def test_visits_are_paired_and_measured(self):
        v = _visits(analyze(EVENTS, PROJECT), "T-0")
        assert [(x.component_uid, x.time_in, x.time_out, x.occupancy) for x in v] == [
            (Y1, 0, 100, 100),
            (T1, 100, 230, 130),
            (S1, 230, 290, 60),
            (T2, 290, 400, 110),
            (Y2, 400, 510, 110),
            (T3, 510, 650, 140),
            (Y1, 650, None, None),
        ]
        assert [x.index for x in v] == list(range(7))

    def test_arrival_and_departure_delay(self):
        v = _visits(analyze(EVENTS, PROJECT), "T-0")
        station = v[2]
        assert (station.scheduled_arrival, station.arrival_delay) == (200, 30)
        assert (station.scheduled_departure, station.departure_delay) == (260, 30)
        assert v[0].departure_delay == 0
        assert v[1].arrival_delay is None and v[1].departure_delay is None

    def test_bridge_component_takes_departure_from_next_route(self):
        y2 = _visits(analyze(EVENTS, PROJECT), "T-0")[4]
        assert y2.scheduled_departure == 500
        assert y2.departure_delay == 10

    def test_revisited_component_is_matched_by_position(self):
        v = _visits(analyze(EVENTS, PROJECT), "T-0")
        assert (v[0].component_uid, v[0].scheduled_departure) == (Y1, 100)
        assert (v[6].component_uid, v[6].scheduled_departure) == (Y1, 700)

    def test_open_visit_has_no_departure_delay(self):
        last = _visits(analyze(EVENTS, PROJECT), "T-0")[6]
        assert last.time_out is None and last.departure_delay is None

    def test_loc_events_are_ignored_for_visits_but_counted(self):
        a = analyze(EVENTS, PROJECT)
        assert a.run.visits == 7 + 3
        assert a.run.events == len(EVENTS)


class TestAggregates:
    def test_component_stats(self):
        c = {x.component_uid: x for x in analyze(EVENTS, PROJECT).components}
        y1 = c[Y1]
        assert (y1.visits, y1.incomplete_visits) == (3, 1)
        assert (y1.occupancy.n, y1.occupancy.mean) == (2, 100)
        # Entries at 0, 0 and 650.
        assert (y1.headway.n, y1.headway.mean, y1.headway.min) == (2, 325, 0)
        assert y1.component_type == "SimpleYard"

        s1 = c[S1]
        assert (s1.visits, s1.incomplete_visits) == (2, 1)
        assert s1.headway.n == 1 and s1.headway.mean == 30
        # T-0: arrived 30 late, left 30 late. T-1: arrived 60 late, still there.
        assert s1.arrival_delay.mean == 45
        assert (s1.departure_delay.n, s1.departure_delay.mean) == (1, 30)

    def test_train_stats(self):
        t = {x.train_uid: x for x in analyze(EVENTS, PROJECT).trains}
        assert t["T-0"].tour == "Tour-A"
        assert (t["T-0"].visits, t["T-0"].incomplete_visits) == (7, 1)
        assert (t["T-0"].first_time_in, t["T-0"].last_time_out) == (0, 650)
        assert t["T-1"].incomplete_visits == 1

    def test_single_value_has_no_std(self):
        c = {x.component_uid: x for x in analyze(EVENTS, PROJECT).components}
        assert c[T3].occupancy.n == 1 and c[T3].occupancy.std is None

    def test_std_is_the_sample_standard_deviation(self):
        c = {x.component_uid: x for x in analyze(EVENTS, PROJECT).components}
        assert c[Y1].headway.std == pytest.approx(459.619, abs=1e-3)  # values 0, 650

    def test_on_time_threshold_boundary(self):
        # Eligible visits: T-0 Y1 (dep 0), S1 (arr 30, dep 30), Y2 (dep 10),
        # T-1 Y1 (dep 0), S1 (arr 60, open). T-0's open Y1 has no delay.
        assert analyze(EVENTS, PROJECT, on_time_threshold=29).run.on_time_pct == 60.0
        assert analyze(EVENTS, PROJECT, on_time_threshold=30).run.on_time_pct == 80.0
        assert analyze(EVENTS, PROJECT, on_time_threshold=60).run.on_time_pct == 100.0
        assert analyze(EVENTS, PROJECT).run.on_time_threshold == 120

    def test_no_scheduled_visits_gives_no_on_time_pct(self):
        c = {x.component_uid: x for x in analyze(EVENTS, PROJECT).components}
        assert c[T1].on_time_pct is None

    def test_run_stats(self):
        r = analyze(EVENTS, PROJECT).run
        assert (r.trains, r.components) == (2, 6)
        assert r.incomplete_visits == 2
        assert (r.first_event_time, r.last_event_time) == (0, 800)

    def test_no_events(self):
        a = analyze([], PROJECT)
        assert a.visits == [] and a.run.events == 0
        assert a.run.first_event_time is None and a.run.on_time_pct is None
        assert [t.train_uid for t in a.trains] == ["T-0", "T-1"]
        assert a.trains[0].visits == 0 and a.trains[0].departure_delay.n == 0


class TestMismatches:
    def test_unknown_train(self):
        with pytest.raises(InputMismatchError, match="not in the project"):
            analyze([ev(0, "IN", "T-9", Y1)], PROJECT)

    def test_wrong_component_for_position(self):
        with pytest.raises(InputMismatchError, match="its tour has"):
            analyze([ev(0, "IN", "T-0", S1)], PROJECT)

    def test_more_visits_than_the_tour_has(self):
        events = [ev(0, "IN", "T-0", Y1)]
        for i, c in enumerate([T1, S1, T2, Y2, T3, Y1, Y1], start=1):
            events.append(ev(i * 10, "IN", "T-0", c))
        with pytest.raises(InputMismatchError):
            analyze(events, PROJECT)

    def test_out_without_in(self):
        with pytest.raises(InputMismatchError, match="no IN events"):
            analyze([ev(0, "OUT", "T-0", Y1)], PROJECT)

    def test_out_before_in(self):
        events = [ev(50, "IN", "T-0", Y1), ev(10, "OUT", "T-0", Y1)]
        with pytest.raises(InputMismatchError, match="does not follow"):
            analyze(events, PROJECT)

    def test_train_with_unknown_tour(self):
        project = dict(PROJECT, trains=[{"name": "T-0", "max_speed": 1, "tour": "nope"}])
        with pytest.raises(InputMismatchError, match="unknown tour"):
            analyze([], project)

    def test_route_args_length_mismatch(self):
        tour = dict(PROJECT["tours"][0])
        tour["routes"] = [{"name": "R1", "args": [None]}]
        with pytest.raises(InputMismatchError, match="args object"):
            analyze([], dict(PROJECT, tours=[tour]))


class TestAgainstTheEngine:
    @staticmethod
    def _project(components, routes, tours, trains):
        return {
            "components": read_components_json(components),
            "routes": read_routes_json(routes),
            "tours": read_tours_json(tours),
            "trains": read_trains_json(trains),
        }

    def test_flattened_schedule_matches_tour_traverse(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        project = self._project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        model = Model.from_project_dictionary(project)
        schedule = _scheduled_segments(project)

        assert set(schedule) == {t["name"] for t in project["trains"]}
        for train in project["trains"]:
            engine = [
                (s.component.uid, s.arrival, s.departure)
                for s in model._tours[train["tour"]].traverse()
            ]
            assert schedule[train["name"]] == engine

    def test_invariants_on_a_seeded_full_day_run(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        project = self._project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )

        def run():
            model = Model.from_project_dictionary(project, seed=11)
            model.start()
            model.run(until=36900)
            model.log_current_state()
            return model, analyze(model.events, model.to_project_dictionary())

        model, a = run()
        n_in = sum(e.event.value == "IN" for e in model.events)
        assert a.run.visits == n_in > 0
        assert all(v.occupancy >= 0 for v in a.visits if v.occupancy is not None)
        # The engine holds trains to their schedule, so none leaves early.
        departure_delays = [
            v.departure_delay for v in a.visits if v.departure_delay is not None
        ]
        assert departure_delays and min(departure_delays) >= 0
        for c in a.components:
            assert c.headway.n == c.visits - 1
        assert sum(c.visits for c in a.components) == a.run.visits
        assert sum(t.visits for t in a.trains) == a.run.visits

        _, again = run()
        assert again.model_dump() == a.model_dump()
