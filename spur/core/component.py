import logging
import math

from simpy import Resource

from spur.core.base import ResourceComponent
from spur.core.jitter import NoJitter


class TimedTrack(ResourceComponent):
    __name__ = "TimedTrack"

    def __init__(
        self, model, uid, traversal_time, capacity=1, jitter=NoJitter()
    ) -> None:
        self.traversal_time = traversal_time
        resource = Resource(model, capacity=capacity)
        super().__init__(model, uid, resource, jitter)

        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    @property
    def traversal_time(self):
        return self._traversal_time

    @traversal_time.setter
    def traversal_time(self, traversal_time):
        traversal_time = int(traversal_time)
        if traversal_time < 0:
            raise ValueError("Travel time must be positive")
        self._traversal_time = traversal_time

    def do(self, train):
        # Simply yield the train as ready to go
        time = self.traversal_time + self._jitter.jitter()
        self.simLog.debug(f"Responding with traversal of {time}")
        yield self.model.timeout(time)


class PhysicsTrack(ResourceComponent):
    __name__ = "PhysicsTrack"

    def __init__(self, model, uid, length, track_speed, jitter=NoJitter()) -> None:
        resource = Resource(model, capacity=1)
        self.track_speed = track_speed
        self.length = length
        super().__init__(model, uid, resource, jitter)
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

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
        # Move the train through a track based on status and top speed

        # # Start by accelerating the train
        time = math.ceil(train.basic_traversal(self.length, self.track_speed))

        self.simLog.debug(f"Traversing me will take {time} steps.")
        yield self.model.timeout(time)


class SimpleYard(ResourceComponent):
    __name__ = "SimpleYard"

    def __init__(self, model, uid, capacity, jitter=NoJitter()) -> None:
        resource = Resource(model, capacity=capacity)
        super().__init__(model, uid, resource, jitter)
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # Simply yield the train as ready to go
        yield self.model.timeout(0)
        self.simLog.debug(f"Train {train.uid} ready to go!")


class SimpleStation(ResourceComponent):
    __name__ = "SimpleStation"

    def __init__(
        self, model, uid, mean_boarding, mean_alighting, jitter=NoJitter()
    ) -> None:
        resource = Resource(model, capacity=1)
        super().__init__(model, uid, resource, jitter)
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # TODO: Implement station logic
        yield self.model.timeout(0)
        self.simLog.error("Station logic not fully implemented!")


class SimpleCrossover(ResourceComponent):
    __name__ = "SimpleCrossover"

    def __init__(self, model, uid, traversal_time, jitter=NoJitter()) -> None:
        self.traversal_time = traversal_time
        resource = Resource(model, capacity=1)
        super().__init__(model, uid, resource, jitter)

    @property
    def traversal_time(self):
        return self._traversal_time

    @traversal_time.setter
    def traversal_time(self, traversal_time):
        traversal_time = int(traversal_time)
        if traversal_time < 0:
            raise ValueError("Traversal time must be positive")
        self._traversal_time = traversal_time

    def do(self, train):
        time = self.traversal_time + self._jitter.jitter()
        yield self.model.timeout(time)
