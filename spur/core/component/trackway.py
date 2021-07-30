import random

from simpy import Resource

from spur.core.base import ResourceComponent


class TestTrack(ResourceComponent):
    __name__ = "Test Section of Track"

    def __init__(self, model, key) -> None:
        resource = Resource(model, capacity=1)
        super().__init__(model, key, resource)

    def _do(self, train):
        """Move a train through the track"""
        time = random.randint(3, 7)
        print(
            f"[{self._model.now}:{self.uid}] moving {train.uid} through will take {time} steps."
        )
        yield self._model.timeout(time)

        # Now we consider it's finished?
        """Finished moving through the track"""
