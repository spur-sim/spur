from spur.core import Model


m = Model()
m.components_from_json("data/models/go_subdivision/components.json")
m.routes_from_json("data/models/go_subdivision/routes.json")
m.trains_from_json("data/models/go_subdivision/trains.json")

m.start()
m.run()
