from spur.core import Model
import os

base_path = "data/models/line4/20220208"

m = Model()
m.add_components_from_json_file(os.path.join(base_path, "components.json"))
m.add_routes_from_json_file(os.path.join(base_path, "routes.json"))
m.add_trains_from_json_file(os.path.join(base_path, "trains.json"))

m.start()
m.run(until=36900)
