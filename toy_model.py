# Set up a toy model

from spur.core import Model
from spur.core.component.trackway import SingleBlockTrack

# Instantiate a model
model = Model()
route = []
route.append(
    model.add_component(SingleBlockTrack, "1", "2", "A", length=40, track_speed=25)
)
route.append(
    model.add_component(SingleBlockTrack, "2", "3", "A", length=30, track_speed=25)
)
route.append(
    model.add_component(SingleBlockTrack, "3", "4", "A", length=450, track_speed=25)
)
route.append(
    model.add_component(SingleBlockTrack, "4", "5", "A", length=1050, track_speed=25)
)
route.append(
    model.add_component(SingleBlockTrack, "5", "6", "A", length=650, track_speed=25)
)
# Plop a train onto the component
train = model.add_train("CX1", "1", "2", "A", max_speed=14, route=route)
train = model.add_train("CX2", "1", "2", "A", max_speed=19, route=route)
train = model.add_train("CX3", "2", "3", "A", max_speed=12, route=route[1:])
model.start()
model.run(until=500)
