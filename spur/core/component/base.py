"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""

from simpy.resources.resource import Resource


class BaseComponent:
    name = "Base Component"

    def __init__(self):
        pass


class Station(BaseComponent, Resource):
    name = "Station"


class Yard(BaseComponent):
    name = "Yard"


class Trackway(BaseComponent, Resource):
    pass


class InterlockingTrack(Trackway):
    name = "Interlocking"


class SignalledTrack(Trackway):
    name = "Block Signalled Track"


class MovingBlockTrack(Trackway):
    name = "Moving Block Controlled Track"


class LadderInterlockingTrack(InterlockingTrack):
    name = "Ladder Interlocking Track"


class CrossingInterlockingTrack(InterlockingTrack):
    name = "Crossing Interlocking Track"
