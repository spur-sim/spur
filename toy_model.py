# Set up a toy model

from spur.core import Model
from spur.core.component.trackway import DummyTrack

# Instantiate a model
model = Model()


# Add some edges with specific components
second = DummyTrack()
first = DummyTrack(next=second)
model.add_component("first", first)
model.add_component("second", second)

model.add_train("MyTrain", first)

model.run(until=100)
