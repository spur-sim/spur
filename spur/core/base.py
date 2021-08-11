"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""
import logging
from abc import ABC, abstractmethod

from simpy.resources.resource import Resource
from simpy.resources.store import Store

logger = logging.getLogger(__name__)


class StatusException(Exception):
    pass


class BaseItem(ABC):
    __name__ = "Base Item"

    def __init__(self, model, uid) -> None:
        self._model = model
        self.uid = uid

        # Set base logging information
        self.logger = logging.getLogger(f"{logger.name}.{uid}")
        self.logger.info("I am alive!")
        # Set simulation logging information
        self.simLog = logging.getLogger("sim.base")

    @property
    def model(self):
        return self._model

    @property
    def uid(self):
        return self._uid

    @uid.setter
    def uid(self, uid):
        self._uid = uid


class BaseComponent(BaseItem, ABC):
    """The base component class used for the model.

    A component represents a physical piece of infrastructure that an agent
    (e.g. a train) moves through. Every component must have a `do()` method
    implemented that the agent interacts with.

    :raises NotImplementedError: Methods that should be implemented but are not
    raise an error.
    """

    __name__ = "Base Component"

    def __init__(self, model, uid, jitter) -> None:
        self._agents = {}
        self._jitter = jitter
        super().__init__(model, uid)

    def __repr__(self):
        return f"Component {self.uid}"

    def accept_agent(self, agent):
        self._agents[agent.uid] = agent
        self.logger.debug(f"Accepted agent {agent.uid}")
        self.logger.debug(f"Current Agents (after accept): {self._agents}")

    def release_agent(self, agent):
        self.logger.debug(f"Releasing agent {agent.uid}")
        self.logger.debug(f"Current Agents (before release): {self._agents}")
        return self._agents.pop(agent.uid)

    @abstractmethod
    def do(self, *args, **kwargs):
        pass


class ResourceComponent(BaseComponent):
    __name__ = "Base Resource Component"

    def __init__(self, model, uid, resource: Resource, jitter) -> None:
        self._res = resource
        super().__init__(model, uid, jitter)

    @property
    def resource(self):
        return self._res


class StoreComponent(BaseComponent):
    __name__ = "Store Component"

    def __init__(self, model, uid, store: Store) -> None:
        self._store = store
        super().__init__(model, uid)


class Agent(BaseItem, ABC):
    __name__ = "Agent"

    def __init__(self, model, uid, route, max_speed) -> None:
        self._current_segment = None  # The current segment
        self.route = route
        self.speed = 0
        self.max_speed = max_speed
        super().__init__(model, uid)

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, speed):
        if speed < 0:
            raise ValueError("Speed must be non-negative")
        self._speed = speed

    @property
    def max_speed(self):
        return self._max_speed

    @max_speed.setter
    def max_speed(self, max_speed):
        if max_speed <= 0:
            raise ValueError("Maximum speed must be positive")
        self._max_speed = max_speed

    @property
    def route(self):
        return self._route

    @route.setter
    def route(self, route):
        self._route = route

    def transfer_to(self, segment):
        # First we tell the previous component we're done
        if self._current_segment:
            self._current_segment.component.release_agent(self)
        # Then we tell the next component we're here
        self._current_segment = segment
        self._current_segment.component.accept_agent(self)

    def start(self):
        self.simLog.info("Started!")
        self.action = self.model.process(self.run())

    @abstractmethod
    def run(self):
        pass
