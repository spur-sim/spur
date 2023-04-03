"""Contains classes describing specific track components and behaviour."""

import logging
import math
from typing import Optional

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


class MultiBlockTrack(ResourceComponent):
    """
    TODO: write docstring content
    """

    __name__ = "MultiBlockTrack"

    def __init__(self, model, uid, num_tracks: int, num_blocks: int, traversal_time, jitter=NoJitter()) -> None:
        self._num_tracks = num_tracks
        self._num_blocks = num_blocks
        self._block_traversal_time = int(math.ceil(traversal_time / num_blocks))  # Round up to integer

        # Track all blocks and all tracks in 2D list
        self._blocks: list[list[Optional[Agent]]] = []
        for i in range(num_tracks):
            track = []
            for j in range(num_blocks):
                track.append(None)
            self._blocks.append(track)

        self._track_directions: list[Optional[int]] = [None] * num_tracks
        self._track_assignments = dict()
        self._train_waiting_events = dict()
        self._resource = SpurResource(model, self, capacity=num_tracks*num_blocks)
        super().__init__(model, uid, self._resource, jitter)
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
                same_dir_tracks.append({"track": t, "empty_count": self._count_empty_from_front(t, direction)})
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
            raise Exception(f"Train {train.uid} cannot enter the component despite being allowed to")

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
            raise Exception("Cannot release the train since it has not yet traversed to the final block")

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
            self._resource.process_queue()
        elif self._blocks[t][b - direction] is not None:
            # If there is a train in previous block, allow it to enter current block
            prev_agent = self._blocks[t][b - direction]
            self._train_waiting_events[prev_agent.uid].succeed()
            self._train_waiting_events[prev_agent.uid] = self._model.event()

        return super().release_agent(agent)

    def check_usage_eligibility(self, agent) -> bool:
        direction = self._get_travel_direction(agent)
        # print(f"Checking eligibility for {agent.uid}: {self._blocks}, {self._track_directions}")

        # Check the current travel direction of each track
        for t, dir_t in enumerate(self._track_directions):
            if dir_t == direction and next(self._iterate_track_blocks(t, direction)) is None:
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
            yield self._model.timeout(self._block_traversal_time)

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
                    self._resource.process_queue()
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
