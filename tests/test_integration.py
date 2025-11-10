import pytest

from spur.core import Model
from spur.io.formats import read_components_json, read_trains_json


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
        m.add_routes_and_tours_from_json_files(routes_json_file, tours_json_file)
        m.add_trains(read_trains_json(trains_json_file))
        m.start()
        m.run(until=until)
        assert m.now == until
