"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""

from simpy.resources.resource import Resource

from spur.core import Model


class BaseComponent:
    __name__ = "Base Component"

    def __init__(self, model: Model, uid) -> None:
        self._model = model
        self._uid = uid
        self._trains = {}

    def _add_train(self, train):
        self._trains[train._uid] = train
        train.component = self

    def _do(self, *args, **kwargs):
        raise NotImplementedError


class ResourceComponent(BaseComponent):
    __name__ = "Base Resource Component"

    def __init__(self, model, key, resource: Resource) -> None:
        self._res = resource
        super().__init__(model, key)

    @property
    def resource(self):
        return self._res


# class BaseComponent:
#     name = "Base Component"

#     def __init__(self, key, prev=None, next=None, trains=[], *args, **kwargs):
#         self.key = key
#         self.prev = prev
#         self.next = next
#         self.trains = []

#     def add_train(self, train):
#         self.trains.append(train)


# class BaseResourceComponent(BaseComponent):
#     name = "Base Resource Component"

#     def __init__(self, key, prev, next, trains, *args, **kwargs):
#         super().__init__(key, prev=prev, next=next, trains=trains, *args, **kwargs)

#     def use(self):
#         raise NotImplementedError


class Station(BaseComponent, Resource):
    name = "Station"
