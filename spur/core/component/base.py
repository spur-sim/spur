"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""

from simpy.resources.resource import Resource


class BaseComponent:
    name = "Base Component"

    def __init__(self, prev=None, next=None, trains=[], *args, **kwargs):
        self.prev = prev
        self.next = next
        self.trains = []

    def add_train(self, train):
        self.trains.append(train)


class Station(BaseComponent, Resource):
    name = "Station"
