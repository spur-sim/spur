
from spur.core import Model
from spur.io.formats import read_components_json, read_routes_json, read_tours_json


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