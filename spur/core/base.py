"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""

from simpy.resources.resource import Resource
from simpy.resources.store import Store


class StatusException(Exception):
    pass


class BaseItem:
    __name__ = "Base Item"

    def __init__(self, model, uid) -> None:
        self._model = model
        self._uid = uid

    @property
    def model(self):
        return self._model

    @property
    def uid(self):
        return self._uid


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

    @property
    def uid(self):
        return self._uid

    # @uid.setter
    # def uid(self, uid):
    #     self._uid = uid

    @property
    def model(self):
        return self._model


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
    __name__ = "Base Agent Type"

    STATUS_STOPPED = 1
    STATUS_MOVING = 2

    def __init__(self, model, uid, route, max_speed, status=STATUS_MOVING) -> None:
        self._component = None
        self.route = route
        self.status = status
        self.max_speed = max_speed
        super().__init__(model, uid)

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        if status not in [self.STATUS_STOPPED, self.STATUS_MOVING]:
            raise StatusException(f"Status code {status} is invalid for agents")
        self._status = status

    @property
    def route(self):
        return self._route

    @route.setter
    def route(self, route):
        self._route = route

    @property
    def max_speed(self):
        return self._max_speed

    @max_speed.setter
    def max_speed(self, max_speed):
        self._max_speed = max_speed

    def start(self):
        self.action = self.model.process(self.run())

    def run(self):
        raise NotImplementedError

    @property
    def current_component(self):
        return self._component

    @current_component.setter
    def current_component(self, c):
        self._component = c

    @property
    def route(self):
        return self._route

    @route.setter
    def route(self, route):
        self._route = route
