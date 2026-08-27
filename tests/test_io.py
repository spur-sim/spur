import json

import pytest

from spur.core import Model
from spur.core.exception import InvalidProjectDataError
from spur.io.formats import (
    read_components_json,
    read_routes_json,
    read_tours_json,
    read_trains_json,
    read_project_json,
    write_project_json,
)


class TestFormats:
    def test_add_components_from_json_file(self, components_json_file):
        m = Model()
        m.add_components(read_components_json(components_json_file))
        assert len(m.components) == 16

    def test_add_routes_and_tours_from_json_file(
        self, components_json_file, routes_json_file, tours_json_file
    ):
        m = Model()
        m.add_components(read_components_json(components_json_file))
        m.add_routes_and_tours(read_routes_json(routes_json_file), read_tours_json(tours_json_file))

    def test_read_trains_json(self, trains_json_file):
        trains = read_trains_json(trains_json_file)
        assert len(trains) == 4
        assert trains[0]["name"] == "T-0"
        assert trains[0]["tour"] == "Tour-1971226"


class TestSchemaValidation:
    def test_invalid_component_missing_key_raises(self, tmp_path):
        bad_file = tmp_path / "bad_components.json"
        bad_file.write_text(json.dumps([{"type": "TimedTrack", "u": "a", "v": "b"}]))
        with pytest.raises(InvalidProjectDataError):
            read_components_json(bad_file)

    def test_invalid_train_negative_speed_raises(self, tmp_path):
        bad_file = tmp_path / "bad_trains.json"
        bad_file.write_text(
            json.dumps([{"name": "T-0", "max_speed": -5, "tour": "Tour-1"}])
        )
        with pytest.raises(InvalidProjectDataError):
            read_trains_json(bad_file)

    def test_invalid_route_wrong_type_raises(self, tmp_path):
        bad_file = tmp_path / "bad_routes.json"
        bad_file.write_text(json.dumps([{"name": "R-1", "components": "not-a-list"}]))
        with pytest.raises(InvalidProjectDataError):
            read_routes_json(bad_file)

    def test_invalid_tour_missing_key_raises(self, tmp_path):
        bad_file = tmp_path / "bad_tours.json"
        bad_file.write_text(json.dumps([{"name": "Tour-1", "routes": []}]))
        with pytest.raises(InvalidProjectDataError):
            read_tours_json(bad_file)


class TestProjectFile:
    def test_write_and_read_project_json_round_trips(
        self,
        tmp_path,
        components_json_file,
        routes_json_file,
        tours_json_file,
        trains_json_file,
    ):
        project = {
            "components": read_components_json(components_json_file),
            "routes": read_routes_json(routes_json_file),
            "tours": read_tours_json(tours_json_file),
            "trains": read_trains_json(trains_json_file),
        }
        m = Model.from_project_dictionary(project)

        out_file = tmp_path / "exported.spur"
        write_project_json(m, str(out_file), name="Test Project")
        reloaded = read_project_json(str(out_file))

        assert reloaded["components"] == project["components"]
        assert reloaded["routes"] == project["routes"]
        assert reloaded["tours"] == project["tours"]
        assert reloaded["trains"] == project["trains"]
