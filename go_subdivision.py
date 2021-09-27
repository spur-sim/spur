from spur.core import Model


m = Model()
m.components_from_json("data/toy_model/component.json")
m.routes_from_json("data/toy_model/route.json")
m.trains_from_json("data/toy_model/train.json")

m.start()
m.run()
