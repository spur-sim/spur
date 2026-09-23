import pytest

from spur.core import Model
from spur.core.event import SimEvent, SimEventType
from spur.io.formats import (
    read_components_json,
    read_routes_json,
    read_tours_json,
    read_trains_json,
)


def _build_model(
    components_json_file,
    routes_json_file,
    tours_json_file,
    trains_json_file,
    **model_kwargs,
):
    m = Model(**model_kwargs)
    m.add_components(read_components_json(components_json_file))
    m.add_routes_and_tours(
        read_routes_json(routes_json_file), read_tours_json(tours_json_file)
    )
    m.add_trains(read_trains_json(trains_json_file))
    return m


def _parse_agent_log(path):
    """Parse `time,logger_name,EVENT,component_uid,component_type` lines
    into `(time, event, component_uid, component_type)` tuples, dropping
    the logger name (structured events carry train_uid separately)."""
    lines = []
    with open(path) as f:
        for line in f:
            time_str, _logger_name, event, component_uid, component_type = (
                line.strip().split(",")
            )
            lines.append((int(time_str), event, component_uid, component_type))
    return lines


class TestSimEvent:
    def test_model_always_populates_events_with_no_sink(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        m = _build_model(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        m.start()
        m.run(until=3600)
        assert len(m.events) > 0
        assert all(isinstance(e, SimEvent) for e in m.events)
        assert {e.event for e in m.events} <= {
            SimEventType.IN,
            SimEventType.OUT,
            SimEventType.LOC,
        }

    def test_event_sink_receives_every_event_in_order(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        sunk = []
        m = _build_model(
            components_json_file,
            routes_json_file,
            tours_json_file,
            trains_json_file,
            event_sink=sunk.append,
        )
        m.start()
        m.run(until=3600)
        assert sunk == m.events

    def test_events_match_agent_log_content_and_order(
        self,
        components_json_file,
        routes_json_file,
        tours_json_file,
        trains_json_file,
        tmp_path,
    ):
        agent_log_file = tmp_path / "agent.log"
        m = _build_model(
            components_json_file,
            routes_json_file,
            tours_json_file,
            trains_json_file,
            agent_log_file=str(agent_log_file),
        )
        m.start()
        m.run(until=3600)
        m.log_current_state()

        log_lines = _parse_agent_log(agent_log_file)
        event_tuples = [
            (e.time, e.event.value, e.component_uid, e.component_type)
            for e in m.events
        ]
        assert event_tuples == log_lines

    def test_from_project_dictionary_forwards_event_sink(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        sunk = []
        project = {
            "components": read_components_json(components_json_file),
            "routes": read_routes_json(routes_json_file),
            "tours": read_tours_json(tours_json_file),
            "trains": read_trains_json(trains_json_file),
        }
        m = Model.from_project_dictionary(project, event_sink=sunk.append)
        m.start()
        m.run(until=3600)
        assert len(sunk) > 0
        assert sunk == m.events
