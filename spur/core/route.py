import logging
from spur.core.base import BaseComponent

# Set up module logger
logger = logging.getLogger(__name__)


class Route:
    def __init__(self) -> None:
        self.segments = []
        self.cursor = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.cursor += 1
        try:
            return self.segments[self.cursor]
        except IndexError:
            raise StopIteration

    @property
    def segments(self):
        return self._segments

    @segments.setter
    def segments(self, segments):
        self._segments = segments

    def append_segment(self, c, arrival=None, departure=None):
        if not isinstance(c, BaseComponent):
            raise TypeError("First arguement must be a child of BaseComponent")
        self.segments.append(RouteSegment(self, c, arrival, departure))


class RouteSegment:
    __name__ = "RouteSegment"

    def __init__(self, route, component, arrival, departure):
        self.logger = logging.getLogger(
            f"{logger.name}.{self.__name__}.{component.uid}"
        )
        self.route = route
        self.arrival = arrival
        self.departure = departure

    @property
    def route(self):
        return self._route

    @route.setter
    def route(self, route):
        self._route = route

    @property
    def component(self):
        return self._component

    @component.setter
    def component(self, component):
        self._component = component

    @property
    def arrival(self):
        return self._arrival

    @arrival.setter
    def arrival(self, arrival):
        self._arrival = arrival

    @property
    def departure(self):
        return self._departure

    @departure.setter
    def departure(self, departure):
        self._departure = departure
