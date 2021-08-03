import logging

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
            self.logger.warn("No current component found")
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
