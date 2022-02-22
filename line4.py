from spur.core import Model
import os

base_path = "data/models/line4/20220208"

m = Model()
m.components_from_json(os.path.join(base_path, "components.json"))
m.routes_from_json(os.path.join(base_path, "routes.json"))
m.trains_from_json(os.path.join(base_path, "trains.json"))

m.start()
m.run(until=36900)
