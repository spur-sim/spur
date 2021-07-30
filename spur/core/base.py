"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""

from simpy.resources.resource import Resource
from simpy.resources.store import Store


class BaseItem:
    __name__ = "Base Item"

    def __init__(self, model, uid) -> None:
        self._model = model
        self._uid = uid

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


class BaseAgent(BaseItem):
    __name__ = "Base Agent Type"

    def __init__(self, model, uid, route) -> None:
        self._component = None
        self._route = route
        super().__init__(model, uid)

    def start(self):
        self.action = self._model.process(self.run())

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
