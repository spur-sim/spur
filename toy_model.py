# Set up a toy model

from spur.core import Model
from spur.core.component.trackway import TestTrack

# Instantiate a model
model = Model()
route = []
route.append(model.add_component(TestTrack, "1", "2", "A"))
route.append(model.add_component(TestTrack, "2", "3", "A"))
# Plop a train onto the component
train = model.add_train("CX1", "1", "2", "A", 50, route=route)
train = model.add_train("CX2", "1", "2", "A", 50, route=route)
model.start()
model.run(until=100)
