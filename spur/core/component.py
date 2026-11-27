"""Contains classes describing specific track components and behaviour."""

import logging
import math
from typing import Optional

from scipy.stats import burr

from spur.core.base import ResourceComponent, SpurResource, Agent
from spur.core.jitter import NoJitter

from spur.core.exception import NotPositiveError

# Marks a block or a station track a train has left that isn't clear yet, so
# no train takes it. It isn't None, so the checks for a free place pass over it.
_CLEARING = type("Clearing", (), {"__repr__": lambda self: "<clearing>"})()


def travel_direction(component, train) -> int:
    """Which way a train crosses a component: 1 from node u to v, -1 from v to u.

    Worked out from the components before and after this one in the train's
    tour, so it must be called before the train has been transferred to
    `component` (its current segment is still the one before).

    Parameters
    ----------
    component : `spur.core.base.BaseComponent`
        The component the train is about to enter
    train : Any child of `Agent` class
        The train about to enter it

    Returns
    -------
    int
        1 if the train travels from u to v, -1 if from v to u
    """
    # When this is called, the current_segment of the train still points to the segment before this one,
    # so it is already the "prev" we want, and the "next" is current_segment's next-next
    if train.current_segment is None:
        # The train has not entered anything yet: this is the first component
        # of its tour, and the one after it says which way it is going.
        try:
            first = train.tour.tour_segments[0].route.segments[0]
            next_c = first.next.component if first.next is not None else None
        except (AttributeError, IndexError):
            next_c = None
        return direction_between(component, None, next_c)
    prev_c = train.current_segment.component
    try:
        next_c = train.current_segment.next.next.component
    except AttributeError:
        next_c = None
    return direction_between(component, prev_c, next_c)


def direction_between(component, prev_c, next_c) -> int:
    """Which way a train crosses a component, given the components it comes from
    and goes to (either may be None): 1 from node u to v, -1 from v to u.

    Parameters
    ----------
    component : `spur.core.base.BaseComponent`
        The component crossed
    prev_c : `spur.core.base.BaseComponent` or None
        The component the train comes from
    next_c : `spur.core.base.BaseComponent` or None
        The component the train goes to

    Returns
    -------
    int
        1 if the train travels from u to v, -1 if from v to u
    """
    c_dict = component.model.component_dictionary()
    u = c_dict[component.uid]["u"]
    v = c_dict[component.uid]["v"]
    prev_u, prev_v = (c_dict[prev_c.uid]["u"], c_dict[prev_c.uid]["v"]) if prev_c else (None, None)
    next_u, next_v = (c_dict[next_c.uid]["u"], c_dict[next_c.uid]["v"]) if next_c else (None, None)

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
    capacity : int, optional
        The number of agents the component can hold at once. Defaults to 1
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
    clearance_time : int, optional
        The model steps a place stays held after a train leaves it, before the next
        train may take it, as for a signalling system to release the route behind
        a train. Defaults to 0
    """

    __name__ = "TimedTrack"
    tags = ("general",)

    def __init__(
        self, model, uid, traversal_time, capacity=1, jitter=NoJitter(), collection=None,
        clearance_time=0,
    ) -> None:
        if traversal_time <= 0:
            raise ValueError("Traversal time must be positive")
        self.traversal_time = traversal_time
        resource = SpurResource(model, self, capacity=capacity)
        super().__init__(model, uid, resource, jitter, collection, clearance_time)

        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

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

    A track normally takes whichever direction its first train is travelling, and is free
    to take the other once it empties. With ``directional`` set, each track is instead
    kept to one direction for good (even-numbered tracks from u to v, odd-numbered from
    v to u), as on ordinary double track.

    Jitter is drawn once for each train's traversal of the whole component and shared
    evenly between its blocks.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    num_tracks : int
        The number of tracks in parallel inside the component
    num_blocks : int
        The number of signal blocks along each track
    traversal_time : int
        The baseline number of model steps to traverse the whole component, divided
        evenly between its blocks
    directional : bool, optional
        Whether each track is kept to one direction: even-numbered tracks from u to
        v, odd-numbered from v to u. Defaults to False
    traversal_time_vu : int, optional
        The baseline number of model steps to traverse the whole component from v
        to u, where that differs (on a gradient, say). Defaults to ``traversal_time``
    jitter_scale_vu : float, optional
        What the jitter is multiplied by for a train travelling from v to u, where
        one direction's times vary more than the other's. Defaults to 1
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
    clearance_time : int, optional
        The model steps a place stays held after a train leaves it, before the next
        train may take it, as for a signalling system to release the route behind
        a train. Defaults to 0
    """

    __name__ = "MultiBlockTrack"
    tags = ("urban", "line")
    _holds_own_places = True

    def __init__(
        self,
        model,
        uid,
        num_tracks: int,
        num_blocks: int,
        traversal_time,
        directional: bool = False,
        traversal_time_vu: Optional[int] = None,
        jitter_scale_vu: float = 1.0,
        jitter=NoJitter(),
        collection=None,
        clearance_time=0,
    ) -> None:
        if num_tracks <= 0 or num_blocks <= 0:
            raise ValueError("Number of tracks and blocks must both be positive")
        if jitter_scale_vu < 0:
            raise ValueError("Jitter scale must be nonnegative")
        self._jitter_scales = {1: 1.0, -1: jitter_scale_vu}
        self._num_tracks = num_tracks
        self._num_blocks = num_blocks
        self._directional = directional
        # Keyed by direction of travel: 1 from u to v, -1 from v to u
        self._traversal_times = {
            1: traversal_time,
            -1: traversal_time if traversal_time_vu is None else traversal_time_vu,
        }
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
        if directional:
            self._track_directions = [1 if t % 2 == 0 else -1 for t in range(num_tracks)]
        self._track_assignments = dict()
        # The time each train will take in each block, set when it enters
        self._train_waiting_events = (
            dict()
        )  # Store SimPy events used to handle wait-queueing of trains between blocks
        resource = SpurResource(model, self, capacity=num_tracks * num_blocks)
        super().__init__(model, uid, resource, jitter, collection, clearance_time)
        # Override the simulation logging information
        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

    def _get_travel_direction(self, train) -> int:
        return travel_direction(self, train)

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

    def _leave_block(self, track: int, block: int, direction: int) -> None:
        """Mark `block` left by a train going `direction`, and free it once clear:
        reset the track's direction if it's empty, and let the train behind in,
        or the trains waiting to enter if it's the entry block."""
        self._blocks[track][block] = _CLEARING

        def free():
            self._blocks[track][block] = None
            # An empty track is free to take either direction, unless it keeps its own
            if not self._directional and self._blocks[track].count(None) == len(self._blocks[track]):
                self._track_directions[track] = None
            start = 0 if direction == 1 else self._num_blocks - 1
            if block == start:
                self._res.process_queue()
            else:
                behind = self._blocks[track][block - direction]
                if isinstance(behind, Agent):
                    self._train_waiting_events[behind.uid].succeed()
                    self._train_waiting_events[behind.uid] = self._model.event()

        self._after_clearance(free)

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
        b = self._num_blocks - 1 if direction == 1 else 0

        if self._blocks[t][b] is not agent:
            raise Exception(
                "Cannot release the train since it has not yet traversed to the final block"
            )

        # Remove train, and free its block once clear
        del self._track_assignments[agent.uid]
        del self._train_waiting_events[agent.uid]
        self._leave_block(t, b, direction)

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

    def _draw_block_times(self, direction: int = 1) -> list:
        """The time to spend in each block for one traversal in a direction.

        Jitter is drawn once for the traversal, so the spread of the whole
        component's traversal time is the jitter's own, however many blocks
        it is divided into. The whole-step times add up to the total.
        """
        jitter = self._jitter.jitter() * self._jitter_scales[direction]
        total = max(0, round(self._traversal_times[direction] + jitter))
        each, extra = divmod(total, self._num_blocks)
        return [each + (1 if b < extra else 0) for b in range(self._num_blocks)]

    def do(self, train):
        assigned_track = self._track_assignments[train.uid]
        direction = self._track_directions[assigned_track]
        block_times = iter(self._draw_block_times(direction))

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
            # Wait to traverse the individual block
            yield self._model.timeout(next(block_times))

            if b != last:
                # If next block is occupied, sleep until woken up
                if self._blocks[assigned_track][b + direction] is not None:
                    yield self._train_waiting_events[train.uid]

                # Next block is clear, shift train over
                self._blocks[assigned_track][b + direction] = train
                self._leave_block(assigned_track, b, direction)


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
    capacity : int
        The number of agents the component can handle
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`

    """

    __name__ = "SimpleYard"
    tags = ("line",)

    def __init__(
        self, model, uid, capacity, jitter=NoJitter(), collection=None
    ) -> None:
        resource = SpurResource(model, self, capacity=capacity)
        super().__init__(model, uid, resource, jitter, collection)
        # Override the simulation logging information
        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

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
    clearance_time : int, optional
        The model steps a place stays held after a train leaves it, before the next
        train may take it, as for a signalling system to release the route behind
        a train. Defaults to 0
    """

    __name__ = "SimpleStation"
    tags = ("general",)

    def __init__(
        self,
        model,
        uid,
        mean_boarding,
        mean_alighting,
        jitter=NoJitter(),
        collection=None,
        clearance_time=0,
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter, collection, clearance_time)
        self._mean_boarding = mean_boarding
        self._mean_alighting = mean_alighting
        # Override the simulation logging information
        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

    def do(self, train):
        # Dwell time model from San2016
        dwell = round(
            2
            + 0.4 * self._mean_boarding
            + 0.4 * self._mean_alighting
            + self._jitter.jitter()
        )
        yield self.model.timeout(dwell)


class DynamicDwellStation(ResourceComponent):
    """A station whose dwell time scales with passenger demand accumulated
    since the previous train's departure, rather than a fixed mean
    boarding/alighting count.

    The number of passengers waiting to board is estimated as the mean
    arrival rate multiplied by the headway since this station's previous
    departure (0 for the first train to visit). Dwell time is then a linear
    function of that estimate: ``coefficient_a + coefficient_b * passengers``,
    where ``coefficient_a`` represents a fixed overhead (e.g. door open/close
    time) and ``coefficient_b`` the marginal dwell time added per boarding
    passenger.

    DynamicDwellStation components have a capacity of 1.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    mean_arrival_rate : float
        The average passenger arrival rate at the station, in passengers per
        model time unit.
    coefficient_a : float
        The fixed dwell time component, independent of passenger volume.
    coefficient_b : float
        The marginal dwell time added per estimated boarding passenger.
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
    clearance_time : int, optional
        The model steps a place stays held after a train leaves it, before the next
        train may take it, as for a signalling system to release the route behind
        a train. Defaults to 0
    """

    __name__ = "DynamicDwellStation"
    tags = ("urban",)

    def __init__(
        self,
        model,
        uid,
        mean_arrival_rate,
        coefficient_a,
        coefficient_b,
        jitter=NoJitter(),
        collection=None,
        clearance_time=0,
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter, collection, clearance_time)
        if mean_arrival_rate < 0:
            raise ValueError("Mean arrival rate must be nonnegative")
        if coefficient_a < 0 or coefficient_b < 0:
            raise ValueError("Dwell time coefficients must be nonnegative")
        self._mean_arrival_rate = mean_arrival_rate
        self._coefficient_a = coefficient_a
        self._coefficient_b = coefficient_b
        self._last_departure = None
        # Override the simulation logging information
        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

    def do(self, train):
        headway = (
            0 if self._last_departure is None else self.model.now - self._last_departure
        )
        passengers = self._mean_arrival_rate * headway
        dwell = round(
            self._coefficient_a
            + self._coefficient_b * passengers
            + self._jitter.jitter()
        )
        self.simLog.debug(
            f"Headway {headway}, estimated {passengers} passengers, dwell {dwell}"
        )
        yield self.model.timeout(dwell)
        self._last_departure = self.model.now


class HeadwayDwellStation(ResourceComponent):
    """A two-track station, one track for each direction, whose dwell time grows
    with the time since the previous train in the same direction.

    Passengers are taken to arrive at a steady rate, so the number boarding and
    alighting is each rate multiplied by the headway: the time since the previous
    train travelling the same way arrived at the station. Dwell time is then
    ``intercept + boarding_time * boarding_rate * headway + alighting_time *
    alighting_rate * headway + jitter``, and never less than zero. The first
    train in a direction has no headway and dwells for ``first_dwell``.

    Each direction has its own track, its own values, and its own record of the
    previous train: values ending ``_uv`` are for trains travelling from node u
    to node v, and ``_vu`` for trains from v to u. A ``_vu`` value left out is
    taken to be the same as its ``_uv`` counterpart.

    A direction may be set not to stop, for a station with a platform on one
    track only. Trains in that direction run through in ``pass_time``.

    One train may be in the station in each direction at a time. After a train
    leaves, its track stays closed to the next train for ``clearance_time``: the
    time the departing train takes to clear the platform and the signal behind
    it to clear.

    .. warning::
        The rates are per model time step, and the times in model time steps,
        so this component is only reasonable if a step is a short, fixed
        length of time such as a second.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    intercept_uv : float
        The dwell time that does not depend on passengers (doors opening and
        closing, say), for trains from u to v
    boarding_rate_uv : float, optional
        Passengers arriving to board trains from u to v, per model time step.
        Defaults to 0
    boarding_time_uv : float, optional
        Dwell time added by each boarding passenger, for trains from u to v.
        Defaults to 0
    alighting_rate_uv : float, optional
        Passengers alighting from trains from u to v, per model time step of
        headway. Defaults to 0
    alighting_time_uv : float, optional
        Dwell time added by each alighting passenger, for trains from u to v.
        Defaults to 0
    first_dwell_uv : float, optional
        The dwell time of the first train from u to v. Defaults to the intercept
    stops_uv : bool, optional
        Whether trains from u to v stop. Defaults to True
    intercept_vu : float, optional
        As ``intercept_uv``, for trains from v to u. Defaults to ``intercept_uv``
    boarding_rate_vu : float, optional
        As ``boarding_rate_uv``, for trains from v to u. Defaults to
        ``boarding_rate_uv``
    boarding_time_vu : float, optional
        As ``boarding_time_uv``, for trains from v to u. Defaults to
        ``boarding_time_uv``
    alighting_rate_vu : float, optional
        As ``alighting_rate_uv``, for trains from v to u. Defaults to
        ``alighting_rate_uv``
    alighting_time_vu : float, optional
        As ``alighting_time_uv``, for trains from v to u. Defaults to
        ``alighting_time_uv``
    first_dwell_vu : float, optional
        The dwell time of the first train from v to u. Defaults to that
        direction's intercept
    stops_vu : bool, optional
        Whether trains from v to u stop. Defaults to True
    pass_time : int, optional
        The time a train that does not stop takes to run through. Defaults to 0
    max_dwell : float, optional
        The longest a train may dwell, before jitter. Defaults to no limit
    clearance_time : int, optional
        How long after a train leaves before the next in the same direction
        may enter. Defaults to 0
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the dwell time. Defaults to `NoJitter`
    collection : The `spur.core.collection.Collection`, optional
        The Collection object the component is a part of. Defaults to None.
    """

    __name__ = "HeadwayDwellStation"
    tags = ("urban", "line")
    _holds_own_places = True

    def __init__(
        self,
        model,
        uid,
        intercept_uv: float,
        boarding_rate_uv: float = 0.0,
        boarding_time_uv: float = 0.0,
        alighting_rate_uv: float = 0.0,
        alighting_time_uv: float = 0.0,
        first_dwell_uv: Optional[float] = None,
        stops_uv: bool = True,
        intercept_vu: Optional[float] = None,
        boarding_rate_vu: Optional[float] = None,
        boarding_time_vu: Optional[float] = None,
        alighting_rate_vu: Optional[float] = None,
        alighting_time_vu: Optional[float] = None,
        first_dwell_vu: Optional[float] = None,
        stops_vu: bool = True,
        pass_time: int = 0,
        max_dwell: Optional[float] = None,
        jitter=NoJitter(),
        collection=None,
        clearance_time: int = 0,
    ) -> None:
        def same(value, default):
            return default if value is None else value

        uv = {
            "intercept": intercept_uv,
            "boarding_rate": boarding_rate_uv,
            "boarding_time": boarding_time_uv,
            "alighting_rate": alighting_rate_uv,
            "alighting_time": alighting_time_uv,
        }
        vu = {
            "intercept": same(intercept_vu, intercept_uv),
            "boarding_rate": same(boarding_rate_vu, boarding_rate_uv),
            "boarding_time": same(boarding_time_vu, boarding_time_uv),
            "alighting_rate": same(alighting_rate_vu, alighting_rate_uv),
            "alighting_time": same(alighting_time_vu, alighting_time_uv),
        }
        for values in (uv, vu):
            if any(value < 0 for value in values.values()):
                raise ValueError("Dwell time values must be nonnegative")
        if pass_time < 0:
            raise ValueError("Pass time must be nonnegative")
        if max_dwell is not None and max_dwell < 0:
            raise ValueError("Maximum dwell must be nonnegative")
        uv["first_dwell"] = same(first_dwell_uv, uv["intercept"])
        vu["first_dwell"] = same(first_dwell_vu, vu["intercept"])
        uv["stops"], vu["stops"] = stops_uv, stops_vu

        # Keyed by direction of travel: 1 from u to v, -1 from v to u
        self._values = {1: uv, -1: vu}
        self._occupant: dict = {1: None, -1: None}
        self._previous_arrival: dict = {1: None, -1: None}
        self._directions: dict = dict()
        self._pass_time = pass_time
        self._max_dwell = max_dwell

        resource = SpurResource(model, self, capacity=2)
        super().__init__(model, uid, resource, jitter, collection, clearance_time)
        # Override the simulation logging information
        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

    def can_accept_agent(self, agent: Agent) -> bool:
        # If the component's collection cannot accept agent, reject the agent outright
        if not super().can_accept_agent(agent):
            return False
        return self._occupant[travel_direction(self, agent)] is None

    def accept_agent(self, agent: Agent):
        direction = travel_direction(self, agent)
        self._occupant[direction] = agent
        self._directions[agent.uid] = direction
        super().accept_agent(agent)

    def release_agent(self, agent: Agent):
        direction = self._directions.pop(agent.uid)
        # The track stays closed to the next train until it has cleared
        self._occupant[direction] = _CLEARING

        def free():
            self._occupant[direction] = None

        self._after_clearance(free)
        return super().release_agent(agent)

    def do(self, train):
        direction = self._directions[train.uid]
        values = self._values[direction]
        if not values["stops"]:
            yield self.model.timeout(self._pass_time)
            return

        previous = self._previous_arrival[direction]
        self._previous_arrival[direction] = self.model.now
        if previous is None:
            dwell = values["first_dwell"]
        else:
            headway = self.model.now - previous
            dwell = (
                values["intercept"]
                + values["boarding_time"] * values["boarding_rate"] * headway
                + values["alighting_time"] * values["alighting_rate"] * headway
            )
        if self._max_dwell is not None:
            dwell = min(dwell, self._max_dwell)
        dwell = max(0, round(dwell + self._jitter.jitter()))
        self.simLog.debug(f"Direction {direction}, dwell {dwell}")
        yield self.model.timeout(dwell)


class MultiTrackStation(ResourceComponent):
    """A station with several tracks, some for stopping trains and some for bypassing ones.

    Stopping trains dwell for a time drawn from a Burr distribution; bypassing trains
    pass through in a fixed time.

    A track normally takes a train going either way. With ``directional`` set, each
    track is kept to one direction, stopping and bypass tracks alike: even-numbered
    tracks for trains from u to v, odd-numbered for trains from v to u, as at a
    station on ordinary double track.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    num_stopping_tracks : int
        The number of tracks used for stopping
    num_bypass_tracks : int
        The number of tracks used for bypassing
    bypass_time : int
        Time taken to bypass through the component
    dwell_c : float
        The 'c' parameter for the Burr distribution of dwell time
    dwell_d : float
        The 'd' parameter for the Burr distribution of dwell time
    dwell_loc : float
        The loc parameter for the Burr distribution of dwell time
    dwell_scale : float
        The scale parameter for the Burr distribution of dwell time
    directional : bool, optional
        Whether each track is kept to one direction: even-numbered tracks from u to
        v, odd-numbered from v to u. Defaults to False
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
    collection : The `spur.core.collection.Collection`, optional
        The Collection object the component is a part of. Defaults to None.
    clearance_time : int, optional
        The model steps a place stays held after a train leaves it, before the next
        train may take it, as for a signalling system to release the route behind
        a train. Defaults to 0
    """

    __name__ = "MultiTrackStation"
    tags = ("urban", "line")
    _holds_own_places = True

    def __init__(
        self,
        model,
        uid,
        num_stopping_tracks: int,
        num_bypass_tracks: int,
        bypass_time: int,
        dwell_c: float,
        dwell_d: float,
        dwell_loc: float,
        dwell_scale: float,
        directional: bool = False,
        jitter=NoJitter(),
        collection=None,
        clearance_time=0,
    ) -> None:
        self._bypass_time = bypass_time
        self._dwell_params = (dwell_c, dwell_d, dwell_loc, dwell_scale)
        self._directional = directional

        self._stopping_tracks: list[Optional[Agent]] = [None] * num_stopping_tracks
        self._bypass_tracks: list[Optional[Agent]] = [None] * num_bypass_tracks
        self._track_assignments: dict[str, str] = dict()

        resource = SpurResource(
            model, self, capacity=num_stopping_tracks + num_bypass_tracks
        )
        super().__init__(model, uid, resource, jitter, collection, clearance_time)
        # Override the simulation logging information
        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

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

    def _direction(self, agent: Agent) -> Optional[int]:
        """The way `agent` is about to cross the station (1 from u to v, -1 from v
        to u), or None if any track will do."""
        return travel_direction(self, agent) if self._directional else None

    @staticmethod
    def _free(tracks: list, direction: Optional[int]) -> list:
        """The free tracks in `tracks` a train going `direction` may use."""
        return [
            t for t, occupant in enumerate(tracks)
            if occupant is None and (direction is None or (1 if t % 2 == 0 else -1) == direction)
        ]

    def accept_agent(self, agent: Agent):
        direction = self._direction(agent)
        # If train is bypassing, first check if there is an available bypass track
        if not self._train_is_stopping(agent, current=False):
            for t in self._free(self._bypass_tracks, direction):
                if self._bypass_tracks[t] is None:
                    self._bypass_tracks[t] = agent
                    self._track_assignments[agent.uid] = f"B-{t}"
                    break

        # If train does not have an assigned track by this point, either it is stopping,
        # or it is bypassing and there is no available bypass track -> try to assign to a stopping track
        if agent.uid not in self._track_assignments:
            for t in self._free(self._stopping_tracks, direction):
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

        tracks = self._stopping_tracks if track_type == "S" else self._bypass_tracks
        tracks[track_index] = _CLEARING

        def free():
            tracks[track_index] = None

        self._after_clearance(free)
        del self._track_assignments[agent.uid]

        return super().release_agent(agent)

    def can_accept_agent(self, agent: Agent) -> bool:
        # If the component's collection cannot accept agent, reject the agent outright
        if not super().can_accept_agent(agent):
            return False

        direction = self._direction(agent)
        stopping = self._free(self._stopping_tracks, direction)
        if self._train_is_stopping(agent, current=False):
            # If train is stopping and there is at least one free stopping track, accept the train
            if stopping:
                return True
        else:
            # If train is bypassing and there is at least one free track of either type, accept the train
            if stopping or self._free(self._bypass_tracks, direction):
                return True

        return False

    def do(self, train):
        if self._train_is_stopping(train, current=True):
            dwell = round(burr.rvs(*self._dwell_params, random_state=self.model.rng) + self._jitter.jitter())
            yield self.model.timeout(dwell)
        else:
            yield self.model.timeout(self._bypass_time + self._jitter.jitter())


class TimedStation(ResourceComponent):
    """Timed station component.

    A timed station simply waits for a specified, fixed set of time.
    Traversal times can be perturbed by provided jitter.

    Attributes
    ----------
    model : `spur.core.model.Model`
        The model controller
    uid : mixed
        The unique component id
    traversal_time : int
        The baseline number of model steps a train dwells at the station
    jitter : `spur.core.jitter.BaseJitter` child, optional
        The Jitter object used to perturb the base time. Defaults to `NoJitter`
    clearance_time : int, optional
        The model steps a place stays held after a train leaves it, before the next
        train may take it, as for a signalling system to release the route behind
        a train. Defaults to 0
    """

    __name__ = "TimedStation"
    tags = ("general",)

    def __init__(
        self,
        model,
        uid,
        traversal_time,
        jitter=NoJitter(),
        collection=None,
        clearance_time=0,
    ) -> None:
        resource = SpurResource(model, self, capacity=1)
        if traversal_time <= 0:
            raise ValueError("Traversal time must be positive")
        self.traversal_time = traversal_time
        super().__init__(model, uid, resource, jitter, collection, clearance_time)
        # Override the simulation logging information
        self.simLog = logging.getLogger(
            f"{model.simLog.name}.track.{self.__name__}.{self.uid}"
        )

    @property
    def traversal_time(self):
        return self._traversal_time

    @traversal_time.setter
    def traversal_time(self, traversal_time):
        if traversal_time <= 0:
            raise NotPositiveError("Traversal time must be positive")
        self._traversal_time = traversal_time

    def do(self, train):
        time = self.traversal_time + self._jitter.jitter()
        self.simLog.debug(f"Dwelling for {time} steps.")
        yield self.model.timeout(time)


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
    clearance_time : int, optional
        The model steps a place stays held after a train leaves it, before the next
        train may take it, as for a signalling system to release the route behind
        a train. Defaults to 0

    Raises
    ------
    NotPositiveError
        If the traversal time is not strictly positive.
    """

    __name__ = "SimpleCrossover"
    tags = ("general",)

    def __init__(
        self, model, uid, traversal_time, jitter=NoJitter(), collection=None,
        clearance_time=0,
    ) -> None:
        if traversal_time <= 0:
            raise ValueError("Traversal time must be positive")
        self.traversal_time = traversal_time
        resource = SpurResource(model, self, capacity=1)
        super().__init__(model, uid, resource, jitter, collection, clearance_time)

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
