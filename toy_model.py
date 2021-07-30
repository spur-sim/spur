# Set up a toy model

from spur.core import Model
from spur.core.component.trackway import TestTrack

# Instantiate a model
model = Model()

model.add_component(TestTrack, "1", "2", "A")
model.add_component(TestTrack, "2", "3", "A")
# Plop a train onto the component
model.add_train("CX745", "1", "2", "A")

print(model.G.edges(data=True, keys=True))
# Add some edges with specific components
# second = DummyTrack(model, "second")

# first = DummyTrack(model, "first", next=second)
# model.add_component(second.key, first)
# model.add_component(first.key, second)

# print(second.key)

# model.add_train("MyTrain", first)

model.start()
model.run(until=100)
