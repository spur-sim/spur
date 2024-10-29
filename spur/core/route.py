"""Contains classes describing routes and route behaviour."""

import logging

# Set up module logger
logger = logging.getLogger(__name__)


class Route:
    """A route object containing a set of components for an agent to traverse.

    Attributes
    ----------
    segments : list
        A list of `RouteSegment` objects to traverse in order
    """

    def __init__(self) -> None:
        self.segments = []

    def __iter__(self):
        return self

    def traverse(self):
        """Traverse the list of segments

        This method traverses through sequential `RouteSegments` and
        provides instruction to the agents.

        Raises
        ------
        StopIteration
            If the segments list is empty on traversal
        """
        if len(self.segments) == 0:
            logger.warn("Trying to traverse an empty list.")
            raise StopIteration
        segment = self.segments[0]
        while segment is not None:
            yield segment
            segment = segment.next

    @property
    def segments(self):
        return self._segments

    @segments.setter
    def segments(self, segments):
        self._segments = segments

    @property
    def previous_segment(self):
        """Get the previous `RouteSegment`. If the route is at the start, the
        segment will be `None`."""
        if self._node < 1:
            return None
        else:
            return self.segments[self._node - 1]

    @property
    def previous_component(self):
        """Get the previous segment component. If the route is at the start, the
        component will be `None`."""
        if self._node < 1:
            return None
        else:
            return self.segments[self._node - 1].component

    @property
    def current_segment(self):
        """Get the current `RouteSegment`. If the route has ended, the
        component will be `None`."""
        try:
            return self.segments[self._node]
        except IndexError:
            return None

    @property
    def current_component(self):
        """Get the current component of the route. If the route has ended,
        the component will be `None`."""
        try:
            return self.segments[self._node].component
        except IndexError:
            return None

    @property
    def next_segment(self):
        """Get the `RouteSegment` following the current one. If this is the end of
        the route, the segment will be `None`."""
        try:
            return self.segments[self._node + 1]
        except IndexError:
            return None

    @property
    def next_component(self):
        """Get the component following the current one. If this is the end of
        the route, the component will be `None`"""
        try:
            return self.segments[self._node + 1].component
        except IndexError:
            return None

    def uids(self):
        """Get a list of all segment component unique IDs in the route.

        :return: list of uids for each component.
        :rtype: list
        """
        return [seg.component.uid for seg in self.traverse()]

    def reset(self):
        """Set the route pointer to the beginning of the route."""
        self._node = 0

    def append(self, component, arrival=None, departure=None):
        """Append a component to the current route. Specified arrival and
        departure times are used to hold trains to a schedule.

        Parameters
        ----------
        component : `BaseComponent`
            The component to append to the route
        arrival : int, optional
            The expected arrival at the component in simulation time, by default `None`
        departure : int, optional
            The permitted departure time from the component in simulation time, by default `None`
        """
        if len(self.segments) == 0:
            prev = None
        else:
            prev = self.segments[-1]
        # Add the segment to the list
        segment = RouteSegment(self, component, prev, None, arrival, departure)
        # Connect the segments together
        if segment.prev:
            segment.prev.next = segment
        # Store them in a list
        self.segments.append(segment)

    def insert(self, component, idx, arrival=None, departure=None):
        """Insert a component to the current route. Specified arrival and
        departure times are used to hold trains to a schedule.

        Parameters
        ----------
        component : `BaseComponent`
            The component to append to the route
        idx : int
            The location in the list to insert the component.
        arrival : int, optional
            The expected arrival at the component in simulation time, by default `None`
        departure : int, optional
            The permitted departure time from the component in simulation time, by default `None`
        """
        next = self.segments[idx]
        # Get the prev pointer
        if idx == 0:
            # Start of the list
            prev = None
        else:
            prev = self.segments[idx - 1]

        segment = RouteSegment(self, component, prev, next, arrival, departure)
        if segment.prev:
            segment.prev.next = segment
        segment.next.prev = segment


class RouteSegment:
    """A class containing information on specific route segments.

    Attributes
    ----------
    route : `spur.core.Route`
        The route the component is a part of
    component : `spur.core.BaseComponent` child
        The component this route segment represents
    prev :  `RouteSegment`
        The previous route segment
    next : `RouteSegment`
        The next route segment
    arrival : int
            The expected arrival at the route segment in simulation time
    departure : int
            The permitted departure time from the route segment in simulation time
    """

    __name__ = "RouteSegment"

    def __init__(self, route, component, prev, next, arrival, departure):
        self.logger = logging.getLogger(
            f"{logger.name}.{self.__name__}.{component.uid}"
        )
        self.route = route
        self.prev = prev
        self.next = next
        self.component = component
        self.arrival = arrival
        self.departure = departure

    def __repr__(self):
        return f"RouteSegment {self.component.uid}"

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
