"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""
import logging

from simpy.resources.resource import Resource
from simpy.resources.store import Store

logger = logging.getLogger(__name__)


class StatusException(Exception):
    pass


class BaseItem:
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


class BaseComponent(BaseItem):
    """The base component class used for the model.

    A component represents a physical piece of infrastructure that an agent
    (e.g. a train) moves through. Every component must have a `_do()` method
    implemented that the agent interacts with.

    :raises NotImplementedError: Methods that should be implemented but are not
    raise an error.
    """

    __name__ = "Base Component"

    def __init__(self, model, uid) -> None:
        self._trains = {}
        super().__init__(model, uid)

    def accept_train(self, train):
        self._trains[train.uid] = train

    def release_train(self, train):
        return self._trains.pop(train.uid)

    def _do(self, *args, **kwargs):
        raise NotImplementedError


class ResourceComponent(BaseComponent):
    __name__ = "Base Resource Component"

    def __init__(self, model, uid, resource: Resource) -> None:
        self._res = resource
        super().__init__(model, uid)

    @property
    def resource(self):
        return self._res


class StoreComponent(BaseComponent):
    __name__ = "Store Component"

    def __init__(self, model, uid, store: Store) -> None:
        self._store = store
        super().__init__(model, uid)


class Agent(BaseItem):
    __name__ = "Agent"

    def __init__(self, model, uid, route, max_speed) -> None:
        self._component = None
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
    def current_component(self):
        return self._component

    @current_component.setter
    def current_component(self, c):
        self._component = c

    @property
    def next_component(self):
        idx = self.route.index(self.current_component)
        if idx == len(self.route) - 1:
            return None
        else:
            return self.route[idx + 1]

    @property
    def route(self):
        return self._route

    @route.setter
    def route(self, route):
        self._route = route

    def start(self):
        self.simLog.info("Started!")
        self.action = self.model.process(self.run())

    def run(self):
        raise NotImplementedError
