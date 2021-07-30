import random

from simpy import Resource

from spur.core.component.base import ResourceComponent


class TestTrack(ResourceComponent):
    __name__ = "Test Section of Track"

    def __init__(self, model, key) -> None:
        resource = Resource(model, capacity=1)
        super().__init__(model, key, resource)

    def _do(self, train):
        """Move a train through the track"""
        print(f"[{self._model.now}] Moving train {train._uid} through the track")
        yield self._model.timeout(random.randint(3, 7))

        # Now we consider it's finished?
        """Finished moving through the track"""


# class TestTrack(ResourceComponent):
#     def __init__(self, model):
#         super().__init__(model)

#     def traverse(self):
#         yield self.model.timeout(10)
#         print(f"A train traversed the {self.key} seciton of track")


# class Trackway(BaseComponent, Resource):
#     def __init__(self, model, *args, **kwargs):
#         print("Trackway Level:", args, kwargs)
#         super().__init__(model, *args, **kwargs)


# class InterlockingTrack(Trackway):
#     name = "Interlocking"


# class SignalledTrack(Trackway):
#     name = "Block Signalled Track"


# class DummyTrack(Trackway):
#     name = "Dummy Track"

#     def __init__(self, *args, **kwargs):
#         print("Dummy Level:", args, kwargs)
#         super().__init__(*args, **kwargs)

#     def traverse(self):
#         yield self.model.timeout(10)
#         print(f"A train traversed the {self.key} seciton of track")


# class MovingBlockTrack(Trackway):
#     name = "Moving Block Controlled Track"


# class LadderInterlockingTrack(InterlockingTrack):
#     name = "Ladder Interlocking Track"


# class CrossingInterlockingTrack(InterlockingTrack):
#     name = "Crossing Interlocking Track"
