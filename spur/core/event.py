"""Structured, in-memory simulation events.

This is the structured counterpart to the optional text-based agent log
(`Model`'s `agent_log_file`/`agentLog`): the same IN/OUT/LOC facts, emitted
as typed objects instead of formatted log lines, so a caller embedding
`spur` as a library can consume simulation results without parsing text.
"""

from enum import Enum

from pydantic import BaseModel


class SimEventType(str, Enum):
    """The kind of thing that happened to a train."""

    IN = "IN"
    OUT = "OUT"
    LOC = "LOC"


class SimEvent(BaseModel):
    """A single structured simulation event.

    Attributes
    ----------
    time : int
        The model's simulation clock value when the event occurred.
    event : SimEventType
        The kind of event.
    train_uid : mixed
        The unique ID of the train the event concerns.
    component_uid : mixed
        The unique ID of the component involved.
    component_type : str
        The class name of the component involved (e.g. `SimpleStation`).
    """

    time: int
    event: SimEventType
    train_uid: str
    component_uid: str
    component_type: str
