from spur.core import Model


m = Model()
# m.components_from_json("data/models/go_sub_simple/components.json")
# m.routes_from_json("data/models/go_sub_simple/routes.json")
# m.trains_from_json("data/models/go_sub_simple/trains.json")
m.start()
m.run()
