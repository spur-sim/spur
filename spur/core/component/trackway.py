import logging
import math

from simpy import Resource

from spur.core.base import ResourceComponent


class BasePhysicsTrack(ResourceComponent):
    __name__ = "BaseTrack"

    def __init__(self, model, uid, length, capacity, track_speed) -> None:
        resource = Resource(model, capacity=capacity)
        self.track_speed = track_speed
        self.length = length
        super().__init__(model, uid, resource)

    @property
    def length(self):
        return self._length

    @length.setter
    def length(self, length):
        if length <= 0:
            raise ValueError("Length must be positive")
        self._length = length

    @property
    def track_speed(self):
        return self._track_speed

    @track_speed.setter
    def track_speed(self, track_speed):
        if track_speed <= 0:
            raise ValueError("Track speed must be positive")
        self._track_speed = track_speed

    def do(self, train):
        raise NotImplementedError


class TimeBlockTrack(ResourceComponent):
    __name__ = "TimeBlock"

    def __init__(self, model, uid, capacity=1) -> None:
        resource = Resource(capacity=capacity)
        super().__init__(model, uid, resource)
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # Simply yield the train as ready to go
        yield self.model.timeout(0)
        self.simLog.debug(f"Train {train.uid} ready to go!")


class SingleBlockTrack(BasePhysicsTrack):
    __name__ = "SingleBlock"

    def __init__(self, model, uid, length, track_speed) -> None:
        super().__init__(model, uid, length, 1, track_speed)
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # Move the train through a track based on status and top speed

        # # Start by accelerating the train
        time = math.ceil(train.basic_traversal(self.length, self.track_speed))

        self.simLog.debug(f"Traversing me will take {time} steps.")
        yield self.model.timeout(time)


class Yard(ResourceComponent):
    __name__ = "Yard"

    def __init__(self, model, uid, capacity) -> None:
        resource = Resource(model, capacity=capacity)
        super().__init__(model, uid, resource)
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # Simply yield the train as ready to go
        yield self.model.timeout(0)
        self.simLog.debug(f"Train {train.uid} ready to go!")
