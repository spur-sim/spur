import logging

from simpy import Interrupt

from spur.core.base import Agent

# Set up module logger
logger = logging.getLogger(__name__)


class Train(Agent):
    """A class used to represent a train agent

    Attributes
    ----------
    tour : `Tour`
        The tour of the train
    """

    __name__ = "train"

    def __init__(self, model, uid, tour, max_speed) -> None:
        """
        Parameters
        ----------
        model : `Model`
            The model the agent is a part of
        uid : mixed
            The unique ID of the agent object
        tour : `Tour`
            The tour of the train
        max_speed : int
            The maximum speed of the train
        """
        super().__init__(model, uid, tour, max_speed)
        self._speed = 0

        # Override base logging information
        self.logger = logging.getLogger(f"{logger.name}.{uid}")

        # Override the simulation logging information
        self.simLog = logging.getLogger(f"{model.simLog.name}.{self.__name__}.{uid}")
        self.simLog.debug("I am alive!")
        # self.simLog.debug(f"Tour: {self.tour.uids()}")

        # Override the agent logging information
        self.agentLog = logging.getLogger(f"{model.agentLog.name}.{self.__name__}.{uid}")

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, speed):
        self._speed = speed

    def __repr__(self):
        return f"Train {self.uid}"

    def run(self):
        """The action method of the train agent.

        Train agents run a simple and continuous process of moving through their
        prescribed tour, alternately requesting access to a component and then
        calling the `do()` method of the component to be processed. SimPy
        `Interrupt`s raised on this process are currently caught and logged
        but otherwise ignored - no delay/reassignment handling is
        implemented yet.
        """
        prev_req = None

        for segment in self.tour.traverse():
            # First let's wait for arrival if needed.
            if segment.arrival is not None:
                try:
                    wait_time = max(0, segment.arrival - self.model.now)
                    self.simLog.debug(
                        f"Arrival | Now: {self.model.now} | Schedule: {segment.arrival} | Wait: {wait_time}"
                    )
                    if wait_time > 0:
                        self.simLog.info(f"Waiting for {wait_time} before arrival")
                    yield self.model.timeout(wait_time)
                except Interrupt:
                    # Future hook: this is where a delay/reassignment
                    # request would be handled (e.g. via a structured
                    # interrupt cause) - currently a no-op.
                    self.simLog.warn("I was interrupted!")
            if not self._current_segment:
                self.simLog.debug(
                    "Not attached. Will try to access to first component."
                )
            # Ask to access the upcoming segment component and accept train once successful
            req = segment.component.resource.request(self)
            yield req
            self.agentLog.info(
                f"IN,{segment.component.uid},{segment.component.__name__}"
            )

            # Release train from old segment component and update current segment
            if self._current_segment:
                self._current_segment.component.release_agent(self)
                # Finished traversing old component
                self.agentLog.info(
                    f"OUT,{self._current_segment.component.uid},{self._current_segment.component.__name__}"
                )
                self.simLog.debug(
                    f"Finished traversing {self._current_segment.component.uid}"
                )
            self._current_segment = segment
            # Release the previous segment's resource once train is in the new segment
            if prev_req is not None:
                segment.prev.component.resource.release(prev_req)

            # Now we get the component to shepherd us through
            try:
                yield self.model.process(self._current_segment.component.do(self))
            except Interrupt:
                self.simLog.warn("I was interrupted!")

            # Now we handle departure times
            if segment.departure is not None:
                try:
                    wait_time = max(0, segment.departure - self.model.now)
                    self.simLog.debug(
                        f"Departure | Now: {self.model.now} | Schedule: {segment.departure} | Wait: {wait_time}"
                    )
                    if wait_time > 0:
                        self.simLog.debug(f"Waiting for {wait_time} before departure")
                    yield self.model.timeout(wait_time)
                except Interrupt:
                    self.simLog.warn("I was interrupted!")

            # Store the Request to be released in the next loop iteration
            prev_req = req

        # End of the tour - Release the agent from the last component and Release the Request from the last segment
        self._current_segment.component.release_agent(self)
        self.agentLog.info(
            f"OUT,{self._current_segment.component.uid},{self._current_segment.component.__name__}"
        )
        self.simLog.debug(f"Finished traversing {self._current_segment.component.uid}")
        self._current_segment.component.resource.release(prev_req)

        self.simLog.debug("Finished my tour, going idle...")
