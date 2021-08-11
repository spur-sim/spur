import logging
import math

from simpy import Interrupt

from spur.core.base import Agent
from spur.core.component import PhysicsTrack

# Set up module logger
logger = logging.getLogger(__name__)


class Train(Agent):
    __name__ = "train"

    def __init__(self, model, uid, route, max_speed) -> None:
        super().__init__(model, uid, route, max_speed)
        self.acceleration = 1.3
        self.deceleration = 1.3
        self._speed = 0

        # Override base logging information
        self.logger = logging.getLogger(f"{logger.name}.{uid}")
        self.logger.info("I am alive!")
        self.logger.debug(f"Route: {self.route.uids()}")
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.{self.__name__}.{uid}")

    def __repr__(self):
        return f"Train {self.uid}"

    def run(self):
        """The action method of the train agent.

        Train agents run a simple and continuous process of moving through their
        prescribed route, alternately requesting access to a component and then
        calling the `do()` method of the component to be processed. Agents can
        be interrupted from their current process and assigned a new route
        before they start running again.
        """
        for segment in self.route.traverse():
            # First let's wait for arrival if needed.
            if segment.arrival is not None:
                try:
                    wait_time = max(0, segment.arrival - self.model.now)
                    self.logger.debug(
                        f"Arrival | Now: {self.model.now} | Schedule: {segment.arrival} | Wait: {wait_time}"
                    )
                    if wait_time > 0:
                        self.simLog.info(f"Waiting for {wait_time} before arrival")
                    yield self.model.timeout(wait_time)
                except Interrupt:
                    self.simLog.warn("I was interrupted!")
            if not self._current_segment:
                self.simLog.warn("Not attached. Will try to access to first component.")
            # Ask to access the first component in the list
            with segment.component.resource.request() as req:
                yield req

                # Transfer to the new segment
                self.transfer_to(segment)

                # Now we get the component to shepherd us through
                try:
                    yield self.model.process(self._current_segment.component.do(self))
                except Interrupt:
                    self.simLog.warn("I was interrupted!")

                # Now we handle departure times
                if segment.departure is not None:
                    try:
                        wait_time = max(0, segment.departure - self.model.now)
                        self.logger.debug(
                            f"Departure | Now: {self.model.now} | Schedule: {segment.departure} | Wait: {wait_time}"
                        )
                        if wait_time > 0:
                            self.simLog.info(
                                f"Waiting for {wait_time} before departure"
                            )
                        yield self.model.timeout(wait_time)
                    except Interrupt:
                        self.simLog.warn("I was interrupted!")

                # Finished traversing
                self.simLog.info(f"Finished traversing {segment.component.uid}")

        self.simLog.info("Finished my route, going idle...")

    def get_basic_traversal_time(self, distance, track_speed, final_speed):

        # Ajudst final requested speed based on our capabilities and allowed
        final_speed = min(final_speed, self.max_speed, track_speed)
        # Adjust the top speed we can make reach on our capabilities and allowed
        max_speed = min(track_speed, self.max_speed)

        self.simLog.debug(
            f"Basic Traversal Calc: (du/step) | Current: {self.speed} | Max: {max_speed} | Final: {final_speed}"
        )

        # Let's look at some cases:
        # If we start below the max, we'll want to accel, cruise, then decel if possible
        accel_dist = ((max_speed * max_speed) - (self.speed * self.speed)) / (
            2 * self.acceleration
        )
        decel_dist = ((max_speed * max_speed) - (final_speed * final_speed)) / (
            2 * self.deceleration
        )

        if accel_dist + decel_dist <= distance:
            self.simLog.debug("Basic acceleration, cruise, deceleration")
            # Simple, we just take three chunks
            accel_time = (max_speed - self.speed) / self.acceleration
            decel_time = (max_speed - final_speed) / self.deceleration
            cruise_time = (distance - accel_dist - decel_dist) / max_speed
            self.speed = final_speed
            return accel_time + decel_time + cruise_time
        else:
            # Going to be an up and a down such that the sum of the two matches the distance
            numerator = (
                distance
                + (self.speed ** 2 / (2 * self.acceleration))
                + (final_speed ** 2) / (2 * self.deceleration)
            )
            denomenator = (1 / (2 * self.acceleration)) + (1 / (2 * self.deceleration))
            v_peak = math.sqrt(numerator / denomenator)
            self.simLog.debug(f"Calculated a vPeak of {v_peak:.3f} du/step")
            time = ((v_peak - self.speed) / self.acceleration) + (
                (v_peak - final_speed) / self.deceleration
            )
            self.speed = final_speed
            return time

    def basic_traversal(self, distance, track_speed):
        """Perform a basic traversal of a cleared distance.

        This method determines the final speed of a train at the end of a
        section of track by examining the next track section for occupancy.
        The method then calls `get_basic_traversal_time` to calculate the time
        taken to accelerate and decelerate and traverse the track.

        :param distance: The length of the track (du).
        :type distance: float
        :param track_speed: The maximum allowable speed on the track (du/step).
        :type track_speed: float
        :return: The time taken to traverse the track (unrounded steps).
        :rtype: float
        """
        # TODO: Add station stop logic in here?
        next_segment = self._current_segment.next
        if next_segment is None:
            # End of the route
            final_speed = 0
        else:
            # Get the next segment's track speed
            if isinstance(next_segment.component, PhysicsTrack):
                # Now we check the occupancy
                if (
                    next_segment.component.resource.count
                    == next_segment.component.resource.capacity
                ):
                    self.simLog.debug(
                        f"Next track component ({next_segment.component.uid}) at capacity. Aiming to stop."
                    )
                    final_speed = 0
                else:
                    final_speed = next_segment.component.track_speed
            else:
                final_speed = 0  # TODO: Handle other components
        return self.get_basic_traversal_time(distance, track_speed, final_speed)
