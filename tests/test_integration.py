from spur.core import Model

import pytest


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
        m.add_components_from_json_file(components_json_file)
        m.add_routes_and_tours_from_json_files(routes_json_file, tours_json_file)
        m.add_trains_from_json_file(trains_json_file)
        m.start()
        m.run(until=until)
        assert m.now == until
