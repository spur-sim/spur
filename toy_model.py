# Set up a toy model

from spur.core import Model
from spur.core.route import Route
from spur.core.component import TimedTrack, SimpleYard, SimpleCrossover, SimpleStation
from spur.core.jitter import UniformJitter

# Instantiate a model
model = Model()

north = Route()
south = Route()
c = model.add_component(SimpleYard, "00", "01", "Y", capacity=10)
north.append(c)
south.append(c)
c = model.add_component(
    TimedTrack, "01", "08", "N", traversal_time=84, jitter=UniformJitter(-5, 5)
)
north.append(c)
c = model.add_component(
    TimedTrack, "01", "08", "S", traversal_time=84, jitter=UniformJitter(-5, 5)
)
south.append(c)
c = model.add_component(SimpleCrossover, "08", "09", "X", traversal_time=5)
north.append(c)
south.append(c)
c = model.add_component(
    SimpleStation, "09", "24", "N", mean_boarding=10, mean_alighting=10
)
north.append(c)
c = model.add_component(
    SimpleStation, "09", "24", "S", mean_boarding=10, mean_alighting=10
)
south.append(c)
c = model.add_component(SimpleYard, "24", "38", "Y", capacity=10)
north.append(c)
south.append(c)

# Plop some trains
train = model.add_train("CX1", max_speed=20, route=north)
train = model.add_train("CX2", max_speed=19, route=south)
model.start()
model.run()
# model.run()
