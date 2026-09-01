"""Contains classes describing tours and tour behaviour."""

import logging
from typing import Iterator, List, Optional

from spur.core.exception import InputMismatchError
from spur.core.route import Route, RouteSegment

# Set up module logger
logger = logging.getLogger(__name__)


class Tour:
    """A tour object containing a set of routes for an agent to traverse.

    Attributes
    ----------
    tour_segments : list
        A list of `TourSegment` objects to traverse in order
    name : str, optional
        An identifying name for the tour, used when exporting a model's
        configuration.
    """

    def __init__(
        self, creation_time: int, deletion_time: int, name: Optional[str] = None
    ) -> None:
        self.tour_segments = []
        self.creation_time = creation_time
        self.deletion_time = deletion_time
        self.name = name

    def __iter__(self) -> "Tour":
        return self

    def traverse(self) -> Iterator[RouteSegment]:
        """Traverse the list of tour segments

        This method traverses through sequential `TourSegments` and
        their `RouteSegments`, and provides instruction to the agents.

        It also merges the last segment of one route with the first of
        the next route (both of which should be the same).

        Yields nothing and returns immediately if the tour segments list,
        or the next tour segment's route, is empty.
        """
        if len(self.tour_segments) == 0:
            logger.warn("Trying to traverse an empty list.")
            return

        tour_segment = self.tour_segments[0]
        route_segment = tour_segment.route.segments[0]
        while tour_segment is not None:
            while route_segment.next is not None:
                yield route_segment
                route_segment = route_segment.next
            # Now we are at the last route segment of the current route
            if tour_segment.next is not None:
                if len(tour_segment.next.route.segments) > 0:
                    # Encode departure time from the bridging component between two routes
                    route_segment.departure = tour_segment.next.route.segments[0].departure
                    # Link two routes together
                    route_segment.next = tour_segment.next.route.segments[1]
                else:
                    # Error checking on empty route segments list for next tour segment
                    logger.warn("The next route in the tour is empty.")
                    return
            yield route_segment
            route_segment = route_segment.next
            tour_segment = tour_segment.next

    @property
    def tour_segments(self) -> List["TourSegment"]:
        return self._tour_segments

    @tour_segments.setter
    def tour_segments(self, tour_segments: List["TourSegment"]) -> None:
        self._tour_segments = tour_segments

    def append(self, route: Route) -> None:
        """Append a route to the current tour.

        Parameters
        ----------
        route : `Route`
            The route to append to the tour
        """
        if len(self.tour_segments) == 0:
            prev = None
        else:
            prev = self.tour_segments[-1]

        # Check if last route component of prev matches with first route component of route being appended
        if prev is not None and prev.route.segments[-1].component.uid != route.segments[0].component.uid:
            raise InputMismatchError(f"Route being appended does not have the same starting component as "
                                     f"the ending component of previous route")

        # Add the segment to the list
        tour_segment = TourSegment(self, route, prev, None)

        # Connect the segments together
        if tour_segment.prev:
            tour_segment.prev.next = tour_segment

        # Store them in a list
        self.tour_segments.append(tour_segment)

    def insert(self, route: Route, idx: int) -> None:
        """Insert a route to the current tour.

        Parameters
        ----------
        route : `Route`
            The route to append to the tour
        idx : int
            The location in the list to insert the route.
        """
        # Check if tour length is zero
        if len(self.tour_segments) == 0:
            # Just append
            self.append(route)
        else:
            next = self.tour_segments[idx]
            # Get the prev pointer
            if idx == 0:
                # Start of the list
                prev = None
            else:
                prev = self.tour_segments[idx - 1]

            tour_segment = TourSegment(self, route, prev, next)
            if tour_segment.prev:
                tour_segment.prev.next = tour_segment
            tour_segment.next.prev = tour_segment
            self.tour_segments.insert(idx, tour_segment)


class TourSegment:
    """A class containing information on specific tour segments.

    Attributes
    ----------
    tour : `spur.core.Tour`
        The tour the route is a part of
    route : `spur.core.Route`
        The route this tour segment represents
    prev :  `TourSegment`
        The previous tour segment
    next : `TourSegment`
        The next tour segment
    """

    __name__ = "TourSegment"

    def __init__(
        self,
        tour: Tour,
        route: Route,
        prev: Optional["TourSegment"],
        next: Optional["TourSegment"],
    ) -> None:
        self.logger = logging.getLogger(
            f"{logger.name}.{self.__name__}.{route.uids()}"
        )
        self._tour = tour
        self._route = route
        self._prev = prev
        self._next = next

    def __repr__(self) -> str:
        return f"TourSegment {self.route.uids()}"

    @property
    def tour(self) -> Tour:
        return self._tour

    @tour.setter
    def tour(self, tour: Tour) -> None:
        self._tour = tour

    @property
    def route(self) -> Route:
        return self._route

    @route.setter
    def route(self, route: Route) -> None:
        self._route = route

    @property
    def prev(self) -> Optional["TourSegment"]:
        return self._prev

    @prev.setter
    def prev(self, prev: Optional["TourSegment"]) -> None:
        self._prev = prev

    @property
    def next(self) -> Optional["TourSegment"]:
        return self._next

    @next.setter
    def next(self, next: Optional["TourSegment"]) -> None:
        self._next = next
