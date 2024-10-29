"""Contains classes describing specific track components and behaviour."""

import logging
import math
from typing import Optional

from scipy.stats import burr

from spur.core.base import ResourceComponent, SpurResource, Agent
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
        self, model, uid, traversal_time, capacity=1, jitter=NoJitter(), collection=None
    ) -> None:

        self.traversal_time = traversal_time
        resource = SpurResource(model, self, capacity=capacity)
        super().__init__(model, uid, resource, jitter, collection)

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

    def __init__(
        self, model, uid, length, track_speed, jitter=NoJitter(), collection=None
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
        self.track_speed = track_speed
        self.length = length
        super().__init__(model, uid, resource, jitter, collection)
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


class MultiBlockTrack(ResourceComponent):
    """A track component that can contain multiple signal blocks and tracks in parallel.

    For each individual track inside the component, the train moves through the successive
    blocks using a Cellular Automaton setup. The traversal time through each block is the
    total component traversal time evenly divided by the number of blocks. After spending
    this duration of time, the train will move to the next block along its direction of
    travel whenever the next block is unoccupied.

    This component assigns each train to a track by putting trains travelling in the same
    direction into the same track as close together as possible, in order to maximize the
    track utilization.
    """

    __name__ = "MultiBlockTrack"

    def __init__(
        self,
        model,
        uid,
        num_tracks: int,
        num_blocks: int,
        traversal_time,
        jitter=NoJitter(),
        collection=None,
    ) -> None:
        self._num_tracks = num_tracks
        self._num_blocks = num_blocks
        self._block_traversal_time = int(
            math.ceil(traversal_time / num_blocks)
        )  # Round up to integer

        # Track all blocks and all tracks in 2D list
        self._blocks: list[list[Optional[Agent]]] = []
        for i in range(num_tracks):
            track = []
            for j in range(num_blocks):
                track.append(None)
            self._blocks.append(track)

        # Record the travel direction of each track as 1 or -1, or None if track empty
        self._track_directions: list[Optional[int]] = [None] * num_tracks
        self._track_assignments = dict()
        self._train_waiting_events = (
            dict()
        )  # Store SimPy events used to handle wait-queueing of trains between blocks
        resource = SpurResource(model, self, capacity=num_tracks * num_blocks)
        super().__init__(model, uid, resource, jitter, collection)
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def _get_travel_direction(self, train) -> int:
        c_dict = self._model.component_dictionary()
        u = c_dict[self._uid]["u"]
        v = c_dict[self._uid]["v"]

        # When this method is called, the current_segment of the train still points to the segment before this one,
        # so it is already the "prev" we want
        try:
            prev_c = train.current_segment.component
            prev_u = c_dict[prev_c.uid]["u"]
            prev_v = c_dict[prev_c.uid]["v"]
        except AttributeError:
            prev_c, prev_u, prev_v = None, None, None

        # The "next" we want is the segment after this one, so it is current_segment's next-next
        try:
            next_c = train.current_segment.next.next.component
            next_u = c_dict[next_c.uid]["u"]
            next_v = c_dict[next_c.uid]["v"]
        except AttributeError:
            next_c, next_u, next_v = None, None, None

        if prev_c is not None and next_c is not None:
            # If node u is shared between current component and previous,
            # and node v is shared between current component and next
            if u in [prev_u, prev_v] and v in [next_u, next_v]:
                # Direction is from u to v
                return 1
            # If node v is shared between current component and previous,
            # and node u is shared between current component and next
            elif v in [prev_u, prev_v] and u in [next_u, next_v]:
                # Direction is from v to u
                return -1

        # If this is the first segment of the train, only look at the next segment
        if prev_c is None:
            if v in [next_u, next_v]:
                return 1
            elif u in [next_u, next_v]:
                return -1

        # If this is the last segment of the train, only look at the previous segment
        if next_c is None:
            if u in [prev_u, prev_v]:
                return 1
            elif v in [prev_u, prev_v]:
                return -1

        raise Exception("Error getting travel direction")

    def _iterate_track_blocks(self, track: int, direction: int):
        if direction == 1:
            start = 0
            end = self._num_blocks
        elif direction == -1:
            start = self._num_blocks - 1
            end = -1
        else:
            raise Exception("Direction has to be 1 or -1")

        for block in range(start, end, direction):
            yield self._blocks[track][block]

    def _count_empty_from_front(self, track: int, direction: int) -> int:
        count = 0

        for b in self._iterate_track_blocks(track, direction):
            if b is not None:
                break
            count += 1

        return count

    def _assign_track(self, train, direction: int) -> int:
        same_dir_tracks: list[dict] = []
        empty_tracks: list[int] = []

        for t, dir_t in enumerate(self._track_directions):
            if dir_t == direction:
                same_dir_tracks.append(
                    {
                        "track": t,
                        "empty_count": self._count_empty_from_front(t, direction),
                    }
                )
            elif dir_t is None:
                empty_tracks.append(t)

        # Prefer tracks already containing a train travelling in the same direction
        if len(same_dir_tracks) > 0:
            # Find the track with the smallest gap behind previous train
            same_dir_tracks = sorted(same_dir_tracks, key=lambda x: x["empty_count"])
            for track in same_dir_tracks:
                # Empty count must be greater than 0; otherwise new train cannot enter
                # Pick the first track with the smallest non-zero empty count
                if track["empty_count"] > 0:
                    return track["track"]

        if len(empty_tracks) == 0:
            raise Exception(
                f"Train {train.uid} cannot enter the component despite being allowed to"
            )

        return empty_tracks[0]

    def accept_agent(self, agent: Agent):
        direction = self._get_travel_direction(agent)

        assigned_track = self._assign_track(agent, direction)
        self._track_assignments[agent.uid] = assigned_track

        if direction == 1:
            start = 0
        else:
            start = self._num_blocks - 1

        self._blocks[assigned_track][start] = agent
        self._track_directions[assigned_track] = direction
        self._train_waiting_events[agent.uid] = self._model.event()

        # print(f"Accepting {agent.uid} on track {assigned_track} with direction {direction}")

        super().accept_agent(agent)

    def release_agent(self, agent: Agent):
        t = self._track_assignments[agent.uid]
        direction = self._track_directions[t]

        # Upon release, train should be located at the final block, depending on the direction
        if direction == 1:
            b = self._num_blocks - 1
            start = 0
        else:
            b = 0
            start = self._num_blocks - 1

        if self._blocks[t][b] is None or self._blocks[t][b].uid != agent.uid:
            raise Exception(
                "Cannot release the train since it has not yet traversed to the final block"
            )

        # Remove train
        self._blocks[t][b] = None
        del self._track_assignments[agent.uid]
        del self._train_waiting_events[agent.uid]

        # If track is now all empty, reset direction info
        if self._blocks[t].count(None) == len(self._blocks[t]):
            self._track_directions[t] = None

        # Take care of the train behind
        if b == start:
            # If leaving starting block, check if trains waiting outside the component could now enter
            self._res.process_queue()
        elif self._blocks[t][b - direction] is not None:
            # If there is a train in previous block, allow it to enter current block
            prev_agent = self._blocks[t][b - direction]
            self._train_waiting_events[prev_agent.uid].succeed()
            self._train_waiting_events[prev_agent.uid] = self._model.event()

        return super().release_agent(agent)

    def can_accept_agent(self, agent) -> bool:
        # If the component's collection cannot accept agent, reject the agent outright
        if not super().can_accept_agent(agent):
            return False

        direction = self._get_travel_direction(agent)
        # print(f"Checking eligibility for {agent.uid}: {self._blocks}, {self._track_directions}")

        # Check the current travel direction of each track
        for t, dir_t in enumerate(self._track_directions):
            if (
                dir_t == direction
                and next(self._iterate_track_blocks(t, direction)) is None
            ):
                # If track direction matches train's and if the entry block is unoccupied, accept the train
                return True
            elif dir_t is None:
                # Or if there is at least one empty track, accept the train
                return True

        # Otherwise, do not accept the train
        return False

    def do(self, train):
        assigned_track = self._track_assignments[train.uid]
        direction = self._track_directions[assigned_track]

        if direction == 1:
            start = 0
            end = self._num_blocks
            last = end - 1
        else:
            start = self._num_blocks - 1
            end = -1
            last = 0

        # Traverse through each block along the assigned track
        for b in range(start, end, direction):
            # Wait to traverse the individual block (with the overall jitter divided by the number of blocks)
            yield self._model.timeout(
                round(
                    self._block_traversal_time
                    + self._jitter.jitter() / self._num_blocks
                )
            )

            if b != last:
                # If next block is occupied, sleep until woken up
                if self._blocks[assigned_track][b + direction] is not None:
                    yield self._train_waiting_events[train.uid]

                # Next block is unoccupied, shift train over
                self._blocks[assigned_track][b + direction] = train
                self._blocks[assigned_track][b] = None

                # Take care of the train behind
                if b == start:
                    # If leaving starting block, check if trains waiting outside the component could now enter
                    self._res.process_queue()
                elif self._blocks[assigned_track][b - direction] is not None:
                    # If there is a train in previous block, allow it to enter current block
                    prev_train = self._blocks[assigned_track][b - direction]
                    self._train_waiting_events[prev_train.uid].succeed()
                    self._train_waiting_events[prev_train.uid] = self._model.event()


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

    def __init__(
        self, model, uid, capacity, jitter=NoJitter(), collection=None
    ) -> None:
        resource = SpurResource(model, self, capacity=capacity)
        super().__init__(model, uid, resource, jitter, collection)
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
        self,
        model,
        uid,
        mean_boarding,
        mean_alighting,
        jitter=NoJitter(),
        collection=None,
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter, collection)
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


class DynamicHeadwayStation(ResourceComponent):
    """Station with dynamic dwell time based on previous train arrivals

    Dynamic headway stations track time between arrivals of trains and compute
    dwell time based on a provided arrival rate.

    This station component has a capacity of 1

    .. warning::
        The DynamicHeadwayStation component is only reasonable if the simulation
        time is in seconds. Note that the first train of the simulation may have
        disproportionately high volumes due to passenger arrival rates.
        Unless a delta is provided.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    arrival_rate : float
        The average number of passengers arriving per time step
    slope : float
        The station-specific coefficient to use for arrival rate.
    intercept : float
        The station-specific intercept value to use for arrival rate.
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
    """

    __name__ = "DynamicHeadwayStation"

    def __init__(
        self,
        model,
        uid,
        boarding_rate: float,
        alighting_rate: float,
        boarding_slope: float,
        alighting_slope: float,
        intercept: float,
        first_train_dwell: int,
        jitter=NoJitter(),
        collection=None,
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter, collection)
        self._boarding_rate = boarding_rate
        self._alighting_rate = alighting_rate
        self._boarding_slope = boarding_slope
        self._alighting_slope = alighting_slope
        self._intercept = intercept
        self._first_train_dwell = first_train_dwell
        self._previous_train_time = None
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def do(self, train):
        # First, compute the total number of passengers
        current_time = self.model.now
        self.simLog.debug(f"Current time recorded at {current_time}")
        if self._previous_train_time is None:
            dwell = self._first_train_dwell
        else:
            self.simLog.info(
                f"Previous arrival recorded at {self._previous_train_time}"
            )
            total_boarding_passengers = (
                current_time - self._previous_train_time
            ) * self._boarding_rate

            total_alighting_passengers = (
                current_time - self._previous_train_time
            ) * self._alighting_rate

            self.simLog.info(f"Total passengers: {total_boarding_passengers}")
            self._previous_train_time = current_time
            dwell = round(
                self._intercept
                + self._boarding_slope * total_boarding_passengers
                + self._alighting_slope * total_alighting_passengers
            )
            self.simLog.info(f"Dwell time: {dwell}")
        yield self.model.timeout(dwell)


class MultiTrackStation(ResourceComponent):
    """
    With Burr dwell time distribution
    """

    __name__ = "MultiTrackStation"

    def __init__(
        self,
        model,
        uid,
        num_stopping_tracks: int,
        num_bypass_tracks: int,
        bypass_time: int,
        dwell_c,
        dwell_d,
        dwell_loc,
        dwell_scale,
        jitter=NoJitter(),
        collection=None,
    ) -> None:
        self._bypass_time = bypass_time
        self._dwell_params = (dwell_c, dwell_d, dwell_loc, dwell_scale)

        self._stopping_tracks: list[Optional[Agent]] = [None] * num_stopping_tracks
        self._bypass_tracks: list[Optional[Agent]] = [None] * num_bypass_tracks
        self._track_assignments: dict[str, str] = dict()

        resource = SpurResource(
            model, self, capacity=num_stopping_tracks + num_bypass_tracks
        )
        super().__init__(model, uid, resource, jitter, collection)
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.track.{self.__name__}.{self.uid}")

    def _train_is_stopping(self, train: Agent, current: bool) -> bool:
        """

        Parameters
        ----------
        train : Any child of `Agent` class
            The train to check
        current : bool
            True if method is called when this component is the current segment of the train;
            False if method is called before train has been transferred to this component

        Returns
        -------
        bool
            True if the train is stopping for boarding and alighting at this station component; False if bypassing
        """
        if current:
            return train.current_segment.departure is not None
        else:
            if train.current_segment is not None:
                return train.current_segment.next.departure is not None
            else:
                # If this is the first component to be visited by the train, can use any track
                return False

    def accept_agent(self, agent: Agent):
        # If train is bypassing, first check if there is an available bypass track
        if not self._train_is_stopping(agent, current=False):
            for t in range(len(self._bypass_tracks)):
                if self._bypass_tracks[t] is None:
                    self._bypass_tracks[t] = agent
                    self._track_assignments[agent.uid] = f"B-{t}"
                    break

        # If train does not have an assigned track by this point, either it is stopping,
        # or it is bypassing and there is no available bypass track -> try to assign to a stopping track
        if agent.uid not in self._track_assignments:
            for t in range(len(self._stopping_tracks)):
                if self._stopping_tracks[t] is None:
                    self._stopping_tracks[t] = agent
                    self._track_assignments[agent.uid] = f"S-{t}"
                    break

        # Train must have a track assigned by this point
        if agent.uid not in self._track_assignments:
            raise Exception(
                f"Train {agent.uid} cannot enter the component despite being allowed to"
            )

        super().accept_agent(agent)

    def release_agent(self, agent: Agent):
        track_type, track_index = self._track_assignments[agent.uid].split("-")
        track_index = int(track_index)

        if track_type == "S":
            self._stopping_tracks[track_index] = None
        else:
            self._bypass_tracks[track_index] = None

        del self._track_assignments[agent.uid]

        return super().release_agent(agent)

    def can_accept_agent(self, agent: Agent) -> bool:
        # If the component's collection cannot accept agent, reject the agent outright
        if not super().can_accept_agent(agent):
            return False

        if self._train_is_stopping(agent, current=False):
            # If train is stopping and there is at least one free stopping track, accept the train
            if self._stopping_tracks.count(None) > 0:
                return True
        else:
            # If train is bypassing and there is at least one free track of either type, accept the train
            if self._bypass_tracks.count(None) + self._stopping_tracks.count(None) > 0:
                return True

        return False

    def do(self, train):
        if self._train_is_stopping(train, current=True):
            dwell = round(burr.rvs(*self._dwell_params) + self._jitter.jitter())
            yield self.model.timeout(dwell)
        else:
            yield self.model.timeout(self._bypass_time + self._jitter.jitter())


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
        collection=None,
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter, collection)
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

    def __init__(
        self, model, uid, traversal_time, jitter=NoJitter(), collection=None
    ) -> None:
        self.traversal_time = traversal_time
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter, collection)

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
