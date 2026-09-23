import pytest

from spur.core import Model
from spur.io.formats import (
    read_components_json,
    read_routes_json,
    read_tours_json,
    read_trains_json,
)


@pytest.mark.parametrize(
    ("until"),
    [
        (3600),
        (8500),
    ],
)
class TestFullModel:
    def test_run(
        self,
        until,
        components_json_file,
        routes_json_file,
        tours_json_file,
        trains_json_file,
    ):
        m = Model()
        m.add_components(read_components_json(components_json_file))
        m.add_routes_and_tours(
            read_routes_json(routes_json_file), read_tours_json(tours_json_file)
        )
        m.add_trains(read_trains_json(trains_json_file))
        m.start()
        m.run(until=until)
        assert m.now == until


class TestFromProjectDictionary:
    @staticmethod
    def _read_project(
        components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        return {
            "components": read_components_json(components_json_file),
            "routes": read_routes_json(routes_json_file),
            "tours": read_tours_json(tours_json_file),
            "trains": read_trains_json(trains_json_file),
        }

    def test_from_project_dictionary_runs(
        self,
        components_json_file,
        routes_json_file,
        tours_json_file,
        trains_json_file,
    ):
        project = self._read_project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        m = Model.from_project_dictionary(project)
        m.start()
        m.run(until=3600)
        assert m.now == 3600

    def test_to_project_dictionary_round_trips(
        self,
        components_json_file,
        routes_json_file,
        tours_json_file,
        trains_json_file,
    ):
        project = self._read_project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        m1 = Model.from_project_dictionary(project)
        exported = m1.to_project_dictionary()

        assert exported == project

        m2 = Model.from_project_dictionary(exported)
        assert len(m2.components) == len(m1.components)
        assert set(m2._tours.keys()) == set(m1._tours.keys())
        assert set(m2.trains.keys()) == set(m1.trains.keys())
