"""Contains classes describing specific track components and behaviour."""

import logging
import math

from spur.core.base import ResourceComponent, SpurResource
from spur.core.jitter import NoJitter

from spur.core.exception import NotPositiveError


class TimedTrack(ResourceComponent):
    """A timed traversal component.

    This component represents a track with a fixed traversal time. Traversal
    times can be perturbed by provided jitter.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    traversal_time : int
        The baseline number of model steps to traverse the component
    capcity : int
        The number of agents the component can handlValueErrorime. Defaults to `NoJitter`
    """

    __name__ = "TimedTrack"

    def __init__(
        self, model, uid, traversal_time, capacity=1, jitter=NoJitter()
    ) -> None:

        self.traversal_time = traversal_time
        resource = SpurResource(model, self, capacity=capacity)
        super().__init__(model, uid, resource, jitter)

        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    @property
    def traversal_time(self):
        return self._traversal_time

    @traversal_time.setter
    def traversal_time(self, traversal_time):
        traversal_time = int(traversal_time)
        if traversal_time < 0:
            raise NotPositiveError("Travel time must be positive")
        self._traversal_time = traversal_time

    def do(self, train):
        # Simply yield the train as ready to go
        time = self.traversal_time + self._jitter.jitter()
        self.simLog.debug(f"Responding with traversal of {time}")
        yield self.model.timeout(time)


class PhysicsTrack(ResourceComponent):
    """A physics-based track component simulating train movement

    This component uses properties of the agent using it to determine
    the length of time to traverse the object.

    **WARNING**: This component is not yet fully developed. Currently only
        has a capcity of 1.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    length : int
        The track length, in model distance units
    track_speed : int
        The maximum track speed, in model distance units per model time step
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`

    Raises
    ------
    NotPositiveError
        If the track length or speed are not strictly positive
    """

    __name__ = "PhysicsTrack"

    def __init__(self, model, uid, length, track_speed, jitter=NoJitter()) -> None:
        resource = SpurResource(model, self, capacity=1)
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
            raise NotPositiveError("Length must be positive")
        self._length = length

    @property
    def track_speed(self):
        return self._track_speed

    @track_speed.setter
    def track_speed(self, track_speed):
        if track_speed <= 0:
            raise NotPositiveError("Track speed must be positive")
        self._track_speed = track_speed

    def do(self, train):
        # Move the train through a track based on status and top speed

        # Start by accelerating the train
        time = math.ceil(train.basic_traversal(self.length, self.track_speed))

        self.simLog.debug(f"Traversing me will take {time} steps.")
        yield self.model.timeout(time)


class SimpleYard(ResourceComponent):
    """A yard component with simple behaviour.

    Yards act as sources or sinks of agents, and are the place where
    agents can be 'spawned' to enter the simulation. Agents placed
    in SimpleYard components are set as ready to attach to a new agent immediately.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    capcity : int
        The number of agents the component can handle
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`

    """

    __name__ = "SimpleYard"

    def __init__(self, model, uid, capacity, jitter=NoJitter()) -> None:
        resource = SpurResource(model, self, capacity=capacity)
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

    SimpleStation components have a capacity of 1

    .. warning::
        The SimpleStation component is only reasonable if the simulation time
        is in seconds.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    mean_boarding : int
        The average number of passengers boarding the train at the station
    mean_alighting : int
        The average number of passengers alighting from the train at the station.
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
    """

    __name__ = "SimpleStation"

    def __init__(
        self, model, uid, mean_boarding, mean_alighting, jitter=NoJitter()
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
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

    **WARNING** This component may not fully work, or may have been
    depreciated.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    mean_boarding : int
        The average number of passengers boarding the train at the station
    mean_alighting : int
        The average number of passengers alighting from the train at the station.
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
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
        resource = SpurResource(model, self, capacity=1)
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
    """A simplified crossover track component.

    This component acts as a 'bottleneck' track
    component with a capacity of 1. It is possible
    to extend the behaviour here to allow for
    directional passing or non-passing as needed.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    traversal_time : int
        The number of time steps required to traverse the component
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`

    Raises
    ------
    NotPositiveError
        If the traversal time is not strictly positive.
    """

    __name__ = "SimpleCrossover"

    def __init__(self, model, uid, traversal_time, jitter=NoJitter()) -> None:
        self.traversal_time = traversal_time
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter)

    @property
    def traversal_time(self):
        return self._traversal_time

    @traversal_time.setter
    def traversal_time(self, traversal_time):
        traversal_time = int(traversal_time)
        if traversal_time < 0:
            raise NotPositiveError("Traversal time must be positive")
        self._traversal_time = traversal_time

    def do(self, train):
        time = self.traversal_time + self._jitter.jitter()
        yield self.model.timeout(time)
