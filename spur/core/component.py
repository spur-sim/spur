"""Contains modules for """
import logging
import math

from simpy import Resource

from spur.core.base import ResourceComponent
from spur.core.jitter import NoJitter


class TimedTrack(ResourceComponent):
    """A timed traversal component.

    This component represents a track with a fixed traversal time. Traversal
    times can be perturbed by provided jitter.

        :param model: The model controller
        :type model: `spur.core.model.Model`
        :param uid: Unique component id
        :type uid: str
        :param traversal_time: Time steps to traverse the component.
        :type traversal_time: int
        :param capacity: Component capacity, defaults to 1
        :type capacity: int, optional
        :param jitter: Jitter for traversal time perturbation, defaults to `NoJitter()`
        :type jitter: `spur.core.jitter.BaseJitter`, optional
    """

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
    """Simple station components.

    Simple stations use a linear combination of boarding and alighting times to
    calcualte dwell times at stations. Currently that model comes from
    San, H.P. and Mohd Masirin, M.I. (2016). Train Dwell Time Models for Rail Passenger Service

    2 + 0.4 * boarding + 0.4 * alighting + jitter

    .. warning::
        The SimpleStation component is only reasonable if the simulation time
        is in seconds.
    """

    __name__ = "SimpleStation"

    def __init__(
        self, model, uid, mean_boarding, mean_alighting, jitter=NoJitter()
    ) -> None:
        resource = Resource(model, capacity=1)
        super().__init__(model, uid, resource, jitter)
        self._mean_boarding = mean_boarding
        self._mean_alighting = mean_alighting
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # Dwell time model from San2016
        dwell = round(
            2
            + 0.4 * self._mean_boarding
            + 0.4 * self._mean_alighting
            + self._jitter.jitter()
        )
        yield self.model.timeout(dwell)


class TimedStation(ResourceComponent):
    """Timed station component.

    A timed station simply waits for a specified set of time.

    :param ResourceComponent: _description_
    :type ResourceComponent: _type_
    :yield: _description_
    :rtype: _type_
    """

    __name__ = "TimedStation"

    def __init__(
        self,
        model,
        uid,
        mean_boarding,
        mean_alighting,
        traversal_time,
        jitter=NoJitter(),
    ) -> None:
        resource = Resource(model, capacity=1)
        super().__init__(model, uid, resource, jitter)
        self._mean_boarding = mean_boarding
        self._mean_alighting = mean_alighting
        self._traversal_time = traversal_time
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # Dwell time model from San2016
        dwell = round(
            2
            + 0.4 * self._mean_boarding
            + 0.4 * self._mean_alighting
            + self._jitter.jitter()
        )
        yield self.model.timeout(dwell)


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
