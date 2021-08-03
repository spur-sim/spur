import random
import logging
import math

from simpy import Resource

from spur.core.base import ResourceComponent


class TestTrack(ResourceComponent):
    __name__ = "TestBlock"

    def __init__(self, model, key) -> None:
        resource = Resource(model, capacity=1)
        super().__init__(model, key, resource)

        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def _do(self, train):
        """Move a train through the track"""
        time = random.randint(3, 7)
        self.simLog.info(f"Moving {train.uid} through will take {time} steps.")
        yield self._model.timeout(time)


class SingleBlockTrack(ResourceComponent):
    __name__ = "SingleBlock"

    def __init__(self, model, uid, length, track_speed) -> None:
        resource = Resource(model, capacity=1)
        self.length = length
        self.track_speed = track_speed
        super().__init__(model, uid, resource)
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

    def _do(self, train):
        # Move the train through a track based on status and top speed

        # # Start by accelerating the train
        time = 0
        distance_remaining = self.length

        # Get the time needed to accelerate the train
        accel_time, accel_distance, truncated = train.accelerate_to(
            self.track_speed, self.length
        )
        time += accel_time  # Traversal time
        distance_remaining -= accel_distance
        current_speed = train.speed

        # # TODO: Handle needing to decelerate?

        # Remaining speed calculation

        time += distance_remaining / current_speed
        time = math.ceil(time)

        self.simLog.debug(f"Traversing me will take {time} steps.")
        yield self._model.timeout(time)
