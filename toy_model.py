# Set up a toy model

from spur.core import Model
from spur.core.route import Route
from spur.core.component import TimedTrack, SimpleYard, SimpleCrossover

# Instantiate a model
model = Model()

north = Route()
south = Route()
c = model.add_component(SimpleYard, "00", "01", "Y", capacity=10)
north.append(c)
south.append(c)
c = model.add_component(TimedTrack, "01", "08", "N", traversal_time=84)
north.append(c)
c = model.add_component(TimedTrack, "01", "08", "S", traversal_time=84)
south.append(c)
c = model.add_component(SimpleCrossover, "08", "09", "X", traversal_time=5)
north.append(c)
south.append(c)
c = model.add_component(SimpleYard, "09", "24", "Y", capacity=10)
north.append(c)
south.append(c)

# Plop some trains
train = model.add_train("CX1", max_speed=20, route=north)
train = model.add_train("CX2", max_speed=19, route=south)
model.start()
model.run()
# model.run()
