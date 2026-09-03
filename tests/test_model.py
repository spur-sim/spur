#!/usr/bin/env python3

import pathlib

from spur import __version__
from spur.core import Model
from spur.core.component import TimedTrack
from spur.core.route import Route
from spur.core.tour import Tour
from spur.core.exception import NotUniqueIDError

from spur.io.formats import read_components_json, read_tours_json, read_routes_json

import pytest

# Tests needed
# - Build and run model with input data (Line 4?)
# - Stop and start model


class TestModelInitialization:
    def test_version(self):
        assert __version__ == "0.0.1"

    def test_initialization(self):
        model = Model()
        print(model)

    def test_not_unique_train_id(self, toy_model_with_components):
        r = Route()
        r.append(toy_model_with_components.components[0])
        r.append(toy_model_with_components.components[1])
        with pytest.raises(NotUniqueIDError):
            toy_model_with_components.add_train(1, 20, r)
            toy_model_with_components.add_train(1, 20, r)


class TestLogCurrentState:
    def test_logs_location_for_trains_in_progress(self, tmp_path):
        agent_log = tmp_path / "agent.log"
        m = Model(agent_log_file=str(agent_log))
        c1 = m._add_component(TimedTrack, "1", "2", "A", traversal_time=100, capacity=1)
        c2 = m._add_component(TimedTrack, "2", "3", "A", traversal_time=100, capacity=1)
        route = Route()
        route.append(c1)
        route.append(c2)
        tour = Tour(creation_time=0, deletion_time=1000)
        tour.append(route)
        m.add_train("T-1", max_speed=50, tour=tour)
        m.start()
        m.run(until=50)  # Train is mid-traversal of c1.

        m.log_current_state()

        loc_lines = [
            line for line in agent_log.read_text().splitlines() if ",LOC," in line
        ]
        assert len(loc_lines) == 1
        assert f"LOC,{c1.uid},TimedTrack" in loc_lines[0]

    def test_skips_trains_that_have_not_started(self, tmp_path):
        agent_log = tmp_path / "agent.log"
        m = Model(agent_log_file=str(agent_log))
        c1 = m._add_component(TimedTrack, "1", "2", "A", traversal_time=100, capacity=1)
        route = Route()
        route.append(c1)
        tour = Tour(creation_time=50, deletion_time=1000)
        tour.append(route)
        m.add_train("T-1", max_speed=50, tour=tour)
        # Note: no start()/run() - the train never begins its tour, so
        # current_segment is still None.

        m.log_current_state()

        assert "LOC" not in agent_log.read_text()
