"""Contains collections that a component could be associated with."""

import logging
from typing import Optional

from spur.core.base import BaseCollection, Agent

# Set up module logger
logger = logging.getLogger(__name__)


class BlockExclusiveZone(BaseCollection):
    """This collection only allows a maximum of one train inside it at any given time.

    This means that all components belonging to this collection must not contain a
    train except for a maximum of one.

    If the collection is occupied, additional trains desiring to enter are put on a
    wait queue.

    Attributes
    ----------
    occupied : bool
        Whether the collection is occupied (i.e. contains a train)
    wait_queue : list[Agent]
        The wait queue for entry into the collection when the collection is already
        occupied.
    """

    __name__ = "BlockExclusiveZone"

    def __init__(self, model, uid):
        self._occupied: bool = False
        self._wait_queue: list[Agent] = []
        super().__init__(model, uid)

    @property
    def occupied(self) -> bool:
        return self._occupied

    @occupied.setter
    def occupied(self, new_state: bool) -> None:
        self._occupied = new_state

    @property
    def wait_queue(self) -> list[Agent]:
        return self._wait_queue

    def add_to_wait_queue(self, agent) -> None:
        """Add a train to the wait queue.

        Parameters
        ----------
        agent : Agent
            The train agent object wanting to enter the collection that is to be added
            to the wait queue.
        """
        self.wait_queue.append(agent)

    def pop_from_wait_queue(self) -> Optional[Agent]:
        """Pop the train at the head of the wait queue, if exists.

        Returns
        -------
        Optional[Agent]
            The train popped from the head of the queue, otherwise None.
        """
        if len(self.wait_queue) == 0:
            return None
        else:
            return self.wait_queue.pop(0)

    def can_accept_agent(self, agent: Agent) -> bool:
        # If agent is staying in the same BEZ, accept the agent by default
        if (
            agent.current_segment is not None
            and agent.current_segment.component.collection is not None
            and agent.current_segment.component.collection.uid == self.uid
        ):
            return True

        # Otherwise, agent is entering BEZ from the outside

        if agent not in self.wait_queue:
            self.add_to_wait_queue(agent)

        if not self.occupied and self.wait_queue[0] == agent:
            return True
        else:
            return False

    def accept_agent(self, agent: Agent) -> None:
        # If agent is staying in the same BEZ, do nothing
        if (
            agent.current_segment is not None
            and agent.current_segment.component.collection is not None
            and agent.current_segment.component.collection.uid == self.uid
        ):
            return

        # Otherwise, agent is entering BEZ from the outside
        if not self.occupied and self.wait_queue[0] == agent:
            self.pop_from_wait_queue()
            self.occupied = True
        else:
            raise Exception(
                f"Cannot complete acceptance of agent {agent.uid} into {self.uid} "
                f"even though it was allowed to enter"
            )

    def release_agent(self, agent: Agent) -> None:
        # If agent is staying in the same BEZ, do nothing
        if (
            agent.current_segment.next is not None
            and agent.current_segment.next.component.collection is not None
            and agent.current_segment.next.component.collection.uid == self.uid
        ):
            return

        # Otherwise, agent is leaving BEZ
        self.occupied = False
        if len(self.wait_queue) > 0:
            # Re-try entry for agent at the head of the BEZ wait queue
            self.wait_queue[0].current_segment.next.component.resource.process_queue()
