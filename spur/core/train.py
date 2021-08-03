import logging
import math

from simpy import Interrupt

from spur.core.base import Agent

# Set up module logger
logger = logging.getLogger(__name__)


class Train(Agent):
    __name__ = "train"

    def __init__(
        self, model, uid, route, max_speed, status=Agent.STATUS_STOPPED
    ) -> None:
        super().__init__(model, uid, route, max_speed, status)
        self.acceleration = 1.3
        self.deceleration = 1.3
        self._speed = 0

        # Override base logging information
        self.logger = logging.getLogger(f"{logger.name}.{uid}")
        self.logger.info("I am alive!")
        # Override the simulation logging information
        self.simLog = logging.getLogger(f"sim.{self.__name__}.{uid}")

    def run(self):
        """The action method of the train agent.

        Train agents run a simple and continuous process of moving through their
        prescribed route, alternately requesting access to a component and then
        calling the `_do()` method of the component to be processed. Agents can
        be interrupted from their current process and assigned a new route
        before they start running again.
        """
        if self.current_component is None:
            self.logger.warn(
                "No current component, will start by accessing first route component."
            )
        for idx, component in enumerate(self.route):
            self.simLog.info(f"Requesting use of {component.uid}")

            # Ask to access the first component in the list
            with component.resource.request() as req:
                yield req

                # We're in. Let's update our own information
                # Release the train from the current component
                if self.current_component is not None:
                    self.current_component.release_train(self)

                component.accept_train(self)
                self.current_component = component

                self.simLog.info(
                    f"Access to {self.current_component._uid} granted, rolling now"
                )
                # Now we get the component to shepherd us through
                try:
                    yield self._model.process(self.current_component._do(self))
                except Interrupt:
                    self.simLog.warn("I was interrupted!")

                # Finished traversing
                self.simLog.info(f"Finished traversing {self.current_component.uid}")
        self.simLog.info("Finished my route, going idle...")

    def step(self, speed):
        yield self._model.timeout(1)

    def accelerate_to(self, speed, max_distance):
        self.logger.debug("Train acceleration requested.")
        target_speed = min(speed, self.max_speed)
        self.logger.debug(
            f"Initial speeds (du/steps) - current: {self.speed:.3f}, max: {self.max_speed:.3f}, requested: {speed:.3f}, target: {target_speed:.3f}"
        )
        time = (target_speed - self.speed) / self.acceleration
        distance = ((target_speed * target_speed) - (self.speed * self.speed)) / (
            2 * self.acceleration
        )
        final_speed = target_speed
        truncated = False
        # Check if we run out of room
        if distance > max_distance:
            self.logger.debug("Max distance exceeded, calculating truncated values.")
            truncated = True
            # Figure out time and final speed
            discr = math.sqrt(self.speed ** 2 + 2 * self.acceleration * max_distance)
            time = ((-1 * self.speed) + discr) / (2 * self.acceleration)
            distance = max_distance
            final_speed = self.speed + self.acceleration * time
        self.speed = final_speed
        self.logger.debug(
            f"Final speeds (du/steps) - current: {self.speed:.3f}, max: {self.max_speed:.3f}, requested: {speed:.3f}, target: {target_speed:.3f}"
        )
        return time, distance, truncated
