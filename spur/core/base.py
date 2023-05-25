"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from simpy.core import BoundClass, Environment
from simpy.resources.resource import Resource, Request, Release
from simpy.resources.store import Store

from spur.core.exception import NotPositiveError, NotUniqueIDError

logger = logging.getLogger(__name__)


class StatusException(Exception):
    pass


class SimLogFilter(logging.Filter):
    def __init__(self, model, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.model = model

    def filter(self, record) -> bool:
        record.now = self.model.now
        record.name = record.name.split(".")[-1]
        return True


class BaseItem(ABC):
    """Abstract base item class for components and agents

    This abstract base class is inhereted by all other simulation objects and
    should not be used directly.

    Attributes
    ----------
    uid : mixed
        A unique identifier for a given item.
    logger : `logging.logger`
    """

    __name__ = "Base Item"

    def __init__(self, model, uid) -> None:
        self._model = model
        if self._model._uid_unique(uid) == False:
            raise NotUniqueIDError(f"UID {uid} has been used already.")
        self.uid = uid

        # Set base logging information
        self.logger = logging.getLogger(f"{logger.name}.{uid}")
        # Set simulation logging information
        self.simLog = logging.getLogger("sim.base")
        self.simLog.debug("I am alive!")

    @property
    def model(self):
        return self._model

    @property
    def uid(self):
        return self._uid

    @uid.setter
    def uid(self, uid):
        self._uid = uid


class BaseComponent(BaseItem, ABC):
    """The base component class used for the model.

    A component represents a physical piece of infrastructure that an agent
    (e.g. a train) moves through. Every component must have a `do()` method
    implemented that the agent interacts with.

    Attributes
    ----------
    collection : Optional['BaseCollection']
        The collection that the component belongs to. Could be None.

    Raises
    ------
    NotImplementedError
        If there are methods that should be overriden and implemented but are not.
    """

    __name__ = "BaseComponent"

    def __init__(self, model, uid, jitter, collection) -> None:
        self._agents = {}
        self._jitter = jitter
        self._collection = collection
        super().__init__(model, uid)

    def __repr__(self):
        return f"Component {self.uid}"

    @property
    def collection(self) -> Optional['BaseCollection']:
        return self._collection

    def accept_agent(self, agent):
        """Accept a request for an agent to use the component

        Parameters
        ----------
        agent : Any child of `BaseAgent` class
            The agent that is requesting use of the component.
        """
        # Acceptance into component means acceptance into collection
        if self.collection is not None:
            self.collection.accept_agent(agent)

        self._agents[agent.uid] = agent

        self.simLog.debug(f"Accepted agent {agent.uid}")
        self.simLog.debug(f"Current Agents (after accept): {self._agents}")

    def release_agent(self, agent):
        """Release an agent from the component resource

        Parameters
        ----------
        agent : Any child of `BaseAgent` class
            The agent that is being released from this component

        Returns
        -------
        `BaseAgent` child
            The agent that has been released from this component.
        """
        # Release from component means release from collection
        if self.collection is not None:
            self.collection.release_agent(agent)

        self.simLog.debug(f"Releasing agent {agent.uid}")
        self.simLog.debug(f"Current Agents (before release): {self._agents}")
        return self._agents.pop(agent.uid)

    def as_dict(self):
        """Return a dictionary describing the attributes of the component

        Returns
        -------
        dict
            A dictionary contianing the required keys and values describing the component.
        """

        d = self.__dict__
        d.pop("_res", None)
        d.pop("_agents", None)
        d.pop("simLog", None)
        d.pop("logger", None)
        d.pop("_model", None)
        # Now build a dictionary with what's left
        clean = {
            "type": self.__name__,
            "uid": d["_uid"],
            "jitter": d["_jitter"].__name__,
        }
        mandatory_keys = ["uid", "jitter"]
        for k in d.keys():
            clean_k = k.lstrip("_")
            if clean_k not in mandatory_keys:
                if "args" not in clean.keys():
                    clean["args"] = {clean_k: d[k]}
                else:
                    clean["args"][clean_k] = d[k]
        return clean

    def can_accept_agent(self, agent: 'Agent') -> bool:
        """Check whether `agent` is eligible to use this component based on component and
        collection states.

        If the component does not belong to a collection, returns True by default, meaning
        the decision to accept the agent's request is purely based on resource capacity.
        Can be overriden in child classes to include custom logic.

        If the component does belong to a collection, determine acceptance based on collection
        state by default. Can be overriden in child classes to include custom logic.

        Parameters
        ----------
        agent : Any child of `Agent` class
            The agent that is requesting use of the component.

        Returns
        -------
        bool
            Whether `agent` is eligible to use the component.
        """
        # If component does not belong to a collection, accept the agent by default
        if self.collection is None:
            return True

        return self.collection.can_accept_agent(agent)

    @abstractmethod
    def do(self, *args, **kwargs):
        raise NotImplementedError("The do method for this object must be overwritten")


class ResourceComponent(BaseComponent):
    __name__ = "Base Resource Component"

    def __init__(self, model, uid, resource: 'SpurResource', jitter, collection) -> None:
        self._res = resource
        super().__init__(model, uid, jitter, collection)

    @property
    def resource(self):
        return self._res


class StoreComponent(BaseComponent):
    __name__ = "Store Component"

    def __init__(self, model, uid, store: Store, jitter, collection) -> None:
        self._store = store
        super().__init__(model, uid, jitter, collection)


class SpurRequest(Request):
    """A custom class that inherits SimPy's Request class.

    This class also stores the agent making the request as a property.

    Attributes
    ----------
    agent : Any child of `Agent` class
        The agent making the request
    """

    def __init__(self, resource: 'SpurResource', agent: 'Agent'):
        self._agent = agent
        super().__init__(resource)

    @property
    def agent(self):
        return self._agent


class SpurResource(Resource):
    """A custom class that inherits SimPy's Resource class.

    This overrides the _do_put() method in the parent class to include a check
    with the linked component regarding whether an agent could use the resource,
    in addition to deciding based on the resource capacity.

    Attributes
    ----------
    component : Any child of `ResourceComponent` class
        The associated component for the resource
    """

    users: List[SpurRequest]

    def __init__(self, env: Environment, component: ResourceComponent, capacity: int = 1):
        self._component = component
        super().__init__(env, capacity)

    if TYPE_CHECKING:

        def request(self, agent: 'Agent' = None) -> SpurRequest:
            """Request a usage slot for the given *agent*."""
            return SpurRequest(self, agent)

        def release(self, request: SpurRequest) -> Release:
            """Release a usage slot."""
            return Release(self, request)

    else:
        request = BoundClass(SpurRequest)
        release = BoundClass(Release)

    def _do_put(self, event: SpurRequest) -> None:
        if (
            len(self.users) < self.capacity
            and self._component.can_accept_agent(event.agent)
        ):
            self.users.append(event)
            self._component.accept_agent(event.agent)
            event.usage_since = self._env.now
            event.succeed()

    def process_queue(self) -> None:
        """Explicitly trigger the processing of the wait queue of trains wanting to use the resource,
        instead of only triggering upon a new request or a train releasing the resource.

        Returns
        -------
        None
        """

        self._trigger_put(None)


class Agent(BaseItem, ABC):
    __name__ = "Agent"

    def __init__(self, model, uid, tour, max_speed) -> None:
        self._current_segment = None  # The current segment
        self.tour = tour
        self.speed = 0
        self.max_speed = max_speed
        super().__init__(model, uid)
        self.agentLog = logging.getLogger("agent")
        self.agentLog.setLevel(logging.INFO)
        # Set up logfile output for agents
        fh = logging.FileHandler("log/agent.log", mode="w")
        fh.setLevel(logging.INFO)
        fh.addFilter(SimLogFilter(model))
        simFileFormatter = logging.Formatter("%(now)d,%(name)s,%(message)s", style="%")
        fh.setFormatter(simFileFormatter)
        self.agentLog.addHandler(fh)

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, speed):
        if speed < 0:
            raise NotPositiveError("Speed must be non-negative")
        self._speed = speed

    @property
    def max_speed(self):
        return self._max_speed

    @max_speed.setter
    def max_speed(self, max_speed):
        if max_speed <= 0:
            raise NotPositiveError("Maximum speed must be positive")
        self._max_speed = max_speed

    @property
    def tour(self):
        return self._tour

    @tour.setter
    def tour(self, tour):
        self._tour = tour

    @property
    def current_segment(self):
        return self._current_segment

    def transfer_to(self, segment):
        # First we tell the previous component we're done
        if self._current_segment:
            self._current_segment.component.release_agent(self)
        # Then we tell the next component we're here
        self._current_segment = segment
        self._current_segment.component.accept_agent(self)

    def start(self):
        self.simLog.debug("Started!")
        self.action = self.model.process(self.run())

    @abstractmethod
    def run(self):
        pass


class BaseCollection(BaseItem, ABC):
    """The base collection class that all collections inherit from."""

    __name__ = "BaseCollection"

    def __init__(self, model, uid) -> None:
        super().__init__(model, uid)

    def __repr__(self) -> str:
        return f"Collection {self.uid}"

    def can_accept_agent(self, agent: Agent) -> bool:
        """Check if the agent can enter the collection. Returns True by default.

        Parameters
        ----------
        agent : Agent
            The agent wanting to enter the collection.

        Returns
        -------
        bool
            Whether the agent is allowed to enter the collection.
        """
        return True

    def accept_agent(self, agent: Agent) -> None:
        """Accept the agent into the collection. Does nothing by default.

        Parameters
        ----------
        agent : Agent
            The agent to be accepted into the collection.
        """
        pass

    def release_agent(self, agent: Agent) -> None:
        """Release the agent from the collection. Does nothing by default.

        Parameters
        ----------
        agent : Agent
            The agent to be released from the collection.
        """
        pass


if __name__ == "__main__":
    pass
