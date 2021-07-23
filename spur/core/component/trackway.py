from simpy.resources.resource import Resource

from spur.core.component.base import BaseComponent


class Trackway(BaseComponent, Resource):
    def __init__(self, capacity, *args, **kwargs):
        super().__init__(*args, **kwargs)


class InterlockingTrack(Trackway):
    name = "Interlocking"


class SignalledTrack(Trackway):
    name = "Block Signalled Track"


class DummyTrack(Trackway):
    name = "Dummy Track"

    def __init__(self, prev=None, next=None, trains=[], capacity=1):
        super().__init__(prev=prev, next=next, trains=trains, capacity=capacity)


class MovingBlockTrack(Trackway):
    name = "Moving Block Controlled Track"


class LadderInterlockingTrack(InterlockingTrack):
    name = "Ladder Interlocking Track"


class CrossingInterlockingTrack(InterlockingTrack):
    name = "Crossing Interlocking Track"
